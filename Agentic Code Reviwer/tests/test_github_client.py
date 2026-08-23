"""Tests for resilient GitHub REST client with mocked HTTP interactions."""

import httpx
import pytest
import respx
from src.github_client import (
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


@respx.mock
def test_fetch_pr_diff_headers():
    """Verifies Accept: application/vnd.github.v3.diff header is transmitted."""
    diff_route = respx.get("https://api.github.com/repos/octocat/Hello-World/pulls/42").respond(
        status_code=200,
        text="diff --git a/test.py b/test.py\n+print('ok')",
    )

    client = GitHubClient(token="mock_token_123")
    diff_text = client.fetch_pr_diff("octocat", "Hello-World", 42)

    assert diff_route.called
    assert diff_route.calls.last.request.headers["Accept"] == "application/vnd.github.v3.diff"
    assert diff_route.calls.last.request.headers["Authorization"] == "Bearer mock_token_123"
    assert "diff --git" in diff_text


@respx.mock
def test_401_unauthorized_raises_auth_error():
    """Verifies 401 response raises GitHubAuthError."""
    respx.get("https://api.github.com/repos/octocat/Hello-World/pulls/1").respond(
        status_code=401,
        json={"message": "Bad credentials"},
    )

    client = GitHubClient(token="invalid_token")
    with pytest.raises(GitHubAuthError):
        client.fetch_pr("octocat", "Hello-World", 1)


@respx.mock
def test_404_not_found_raises_not_found_error():
    """Verifies 404 response raises GitHubNotFoundError."""
    respx.get("https://api.github.com/repos/octocat/Hello-World/pulls/999").respond(
        status_code=404,
        json={"message": "Not Found"},
    )

    client = GitHubClient(token="valid_token")
    with pytest.raises(GitHubNotFoundError):
        client.fetch_pr("octocat", "Hello-World", 999)


@respx.mock
def test_rate_limit_retry_and_exhaustion(monkeypatch):
    """Verifies rate-limit detection on 429 and exhaustion raises GitHubRateLimitError."""
    monkeypatch.setattr("time.sleep", lambda s: None)

    respx.get("https://api.github.com/repos/octocat/Hello-World/pulls/10").respond(
        status_code=429,
        headers={"retry-after": "1"},
        json={"message": "API rate limit exceeded"},
    )

    client = GitHubClient(token="token", max_retries=2)
    with pytest.raises(GitHubRateLimitError):
        client.fetch_pr("octocat", "Hello-World", 10)


@respx.mock
def test_post_review_payload():
    """Verifies line-level comment submission payload format."""
    review_route = respx.post("https://api.github.com/repos/octocat/Hello-World/pulls/7/reviews").respond(
        status_code=200,
        json={"id": 101, "state": "COMMENTED"},
    )

    client = GitHubClient(token="token")
    comments = [
        {"path": "src/main.py", "line": 42, "body": "Potential null reference here."}
    ]
    resp = client.post_review(
        owner="octocat",
        repo="Hello-World",
        pr_number=7,
        commit_id="sha123abc",
        body="PR Sage automated review.",
        event="COMMENT",
        comments=comments,
    )

    assert review_route.called
    payload = review_route.calls.last.request.read().decode()
    assert "sha123abc" in payload
    assert "Potential null reference" in payload
    assert resp["id"] == 101
