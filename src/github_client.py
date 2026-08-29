"""Resilient GitHub REST API client for PR Sage using httpx.

Interview Rationale (WHY):
- Rate-Limit and Backoff Intelligence: Intercepts GitHub 429/403 rate limits and transient 5xx server errors,
  recalculating wait times via `x-ratelimit-reset` and `Retry-After` headers before retrying with exponential backoff.
- Unified Diff Endpoint: Fetches exact PR unified diffs via `Accept: application/vnd.github.v3.diff` without
  requiring a local git clone or high-memory repository pulls.
- Non-Blocking Review API: Submits reviews using `event="COMMENT"` with line-level `PullRequestReviewComment` objects,
  allowing authors to inspect suggestions without blocking PR merges.
"""

from __future__ import annotations

import logging
import time
from typing import Any
import httpx


logger = logging.getLogger("pr_sage.github_client")


# =====================================================================
# Custom Exception Hierarchy
# =====================================================================


class GitHubAPIError(Exception):
    """Base exception for all GitHub REST API communication failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GitHubAuthError(GitHubAPIError):
    """Raised when authentication credentials (GITHUB_TOKEN) are invalid or missing (HTTP 401)."""


class GitHubNotFoundError(GitHubAPIError):
    """Raised when the specified repository or PR does not exist or token lacks access (HTTP 404)."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub API rate limit is exceeded and all retries are exhausted (HTTP 403/429)."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code)
        self.retry_after = retry_after


# =====================================================================
# GitHub Client Implementation
# =====================================================================


class GitHubClient:
    """Client for interacting with GitHub REST API v3."""

    def __init__(
        self,
        token: str = "",
        base_url: str = "https://api.github.com",
        timeout: float = 30.0,
        max_retries: int = 3,
        client: httpx.Client | None = None,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(1, max_retries)

        default_headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PR-Sage-Agentic-Reviewer",
        }
        if self.token:
            default_headers["Authorization"] = f"Bearer {self.token}"

        self._client = client or httpx.Client(
            headers=default_headers,
            timeout=self.timeout,
            follow_redirects=True,
        )

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Closes the underlying HTTP client session."""
        self._client.close()

    def _resolve_url(self, path_or_url: str) -> str:
        """Resolves relative API path against base_url."""
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        clean_path = path_or_url.lstrip("/")
        return f"{self.base_url}/{clean_path}"

    def _request(
        self,
        method: str,
        path_or_url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executes an HTTP request with exponential backoff and rate-limit handling."""
        url = self._resolve_url(path_or_url)
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = self._client.request(method, url, **kwargs)

                # 1. Successful HTTP responses
                if response.is_success:
                    return response

                # 2. Authentication failure (401)
                if response.status_code == 401:
                    raise GitHubAuthError(
                        f"GitHub authentication failed (401). Check GITHUB_TOKEN permissions: {response.text}",
                        status_code=401,
                    )

                # 3. Not Found (404)
                if response.status_code == 404:
                    raise GitHubNotFoundError(
                        f"GitHub resource not found (404) at '{url}': {response.text}",
                        status_code=404,
                    )

                # 4. Rate Limiting (403 with zero remaining or 429)
                is_rate_limited = response.status_code == 429 or (
                    response.status_code == 403
                    and (
                        response.headers.get("x-ratelimit-remaining") == "0"
                        or "rate limit" in response.text.lower()
                    )
                )

                if is_rate_limited:
                    retry_after = self._calculate_rate_limit_wait(response, attempt)
                    if attempt + 1 < self.max_retries:
                        logger.warning(
                            f"GitHub rate limit hit on attempt {attempt + 1}/{self.max_retries}. Backing off for {retry_after:.1f}s."
                        )
                        time.sleep(retry_after)
                        continue
                    raise GitHubRateLimitError(
                        f"GitHub rate limit exceeded after {self.max_retries} attempts: {response.text}",
                        status_code=response.status_code,
                        retry_after=retry_after,
                    )

                # 5. Transient Server Errors (500, 502, 503, 504)
                if response.status_code in (500, 502, 503, 504):
                    if attempt + 1 < self.max_retries:
                        backoff = (2**attempt) * 0.5
                        logger.warning(
                            f"GitHub server error ({response.status_code}) on attempt {attempt + 1}. Retrying in {backoff:.1f}s."
                        )
                        time.sleep(backoff)
                        continue
                    raise GitHubAPIError(
                        f"GitHub server error ({response.status_code}) on '{url}': {response.text}",
                        status_code=response.status_code,
                    )

                # 6. Other 4xx Client Errors
                raise GitHubAPIError(
                    f"GitHub API error ({response.status_code}) on '{url}': {response.text}",
                    status_code=response.status_code,
                )

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_exception = exc
                if attempt + 1 < self.max_retries:
                    backoff = (2**attempt) * 0.5
                    logger.warning(
                        f"Network transport error ({exc}) on attempt {attempt + 1}. Retrying in {backoff:.1f}s."
                    )
                    time.sleep(backoff)
                    continue
                break

        raise GitHubAPIError(
            f"Failed to communicate with GitHub after {self.max_retries} retries: {last_exception}"
        )

    def _calculate_rate_limit_wait(self, response: httpx.Response, attempt: int) -> float:
        """Determines sleep time from Retry-After or x-ratelimit-reset headers with exponential fallback."""
        retry_after_hdr = response.headers.get("retry-after")
        if retry_after_hdr and retry_after_hdr.isdigit():
            return min(float(retry_after_hdr), 60.0)

        reset_hdr = response.headers.get("x-ratelimit-reset")
        if reset_hdr and reset_hdr.isdigit():
            wait = max(0.0, float(reset_hdr) - time.time())
            return min(wait + 1.0, 60.0)

        return min((2**attempt) * 1.0, 60.0)

    # =================================================================
    # High-Level API Methods
    # =================================================================

    def fetch_pr(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        """Fetches metadata for a pull request (title, body, author, head/base commits)."""
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}"
        response = self._request("GET", endpoint)
        return response.json()  # type: ignore[no-any-return]

    def fetch_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Fetches the unified git diff for a pull request."""
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}"
        diff_headers = {"Accept": "application/vnd.github.v3.diff"}
        response = self._request("GET", endpoint, headers=diff_headers)
        return response.text

    def fetch_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetches the full list of files changed in a pull request with pagination."""
        files: list[dict[str, Any]] = []
        page = 1
        per_page = 100

        while True:
            endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/files"
            params = {"per_page": per_page, "page": page}
            response = self._request("GET", endpoint, params=params)
            page_data: list[dict[str, Any]] = response.json()

            if not page_data:
                break

            files.extend(page_data)
            if len(page_data) < per_page:
                break
            page += 1

        return files

    def post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        commit_id: str,
        body: str,
        event: str = "COMMENT",
        comments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Submits a multi-line pull request review with line-level comments."""
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        payload = {
            "commit_id": commit_id,
            "body": body,
            "event": event,
            "comments": comments or [],
        }
        response = self._request("POST", endpoint, json=payload)
        return response.json()  # type: ignore[no-any-return]

    def post_pr_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> dict[str, Any]:
        """Posts a standard top-level comment on the PR issue thread."""
        endpoint = f"repos/{owner}/{repo}/issues/{pr_number}/comments"
        payload = {"body": body}
        response = self._request("POST", endpoint, json=payload)
        return response.json()  # type: ignore[no-any-return]
