"""CLI entrypoint for PR Sage Agentic AI Code Reviewer."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from dotenv import load_dotenv
from src.agent import PRSageAgent
from src.config import Settings
from src.github_client import GitHubClient
from src.llm import LLMClient


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parses command-line flags and parameters."""
    parser = argparse.ArgumentParser(
        prog="pr-sage",
        description="PR Sage: Multi-Step Agentic AI Code Reviewer for GitHub Pull Requests",
    )
    parser.add_argument(
        "--pr-number",
        type=int,
        default=None,
        help="Target GitHub Pull Request number to review.",
    )
    parser.add_argument(
        "--file",
        type=str,
        default="",
        help="Review a local file or demo file directly (e.g. demo/pr_vulnerable.py).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        default=False,
        help="Run review on demo/pr_vulnerable.py.",
    )
    parser.add_argument(
        "--owner",
        type=str,
        default="",
        help="GitHub repository owner (defaults to REPO env variable).",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="",
        help="GitHub repository name or 'owner/repo' format.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run analysis locally and output findings to review_output.json without posting to GitHub.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="",
        help="Override Groq LLM model name (defaults to Settings.MODEL_NAME).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="",
        help="Override Groq base URL (defaults to Settings.GROQ_BASE_URL).",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Main execution function."""
    load_dotenv()
    parsed_args = parse_args(args)

    # Initialize Settings with overrides
    overrides: dict[str, Any] = {}
    if parsed_args.dry_run or parsed_args.file or parsed_args.demo or parsed_args.pr_number is None:
        overrides["DRY_RUN"] = True
    if parsed_args.model:
        overrides["MODEL_NAME"] = parsed_args.model
    if parsed_args.base_url:
        overrides["GROQ_BASE_URL"] = parsed_args.base_url
    if parsed_args.repo and "/" in parsed_args.repo:
        overrides["REPO"] = parsed_args.repo

    settings = Settings(**overrides)

    github = GitHubClient(
        token=settings.GITHUB_TOKEN,
        timeout=settings.REQUEST_TIMEOUT,
        max_retries=settings.MAX_RETRIES,
    )
    llm = LLMClient(
        model=settings.MODEL_NAME,
        api_key=settings.GROQ_API_KEY,
        base_url=settings.GROQ_BASE_URL,
        timeout=settings.REQUEST_TIMEOUT,
        max_retries=settings.MAX_RETRIES,
    )

    agent = PRSageAgent(settings=settings, github=github, llm=llm)

    try:
        if parsed_args.demo or (not parsed_args.file and parsed_args.pr_number is None):
            target = parsed_args.file or "demo/pr_vulnerable.py"
            agent.review_file(target)
            return 0
        elif parsed_args.file:
            agent.review_file(parsed_args.file)
            return 0
        else:
            agent.run(
                pr_number=parsed_args.pr_number,
                owner=parsed_args.owner or None,
                repo=parsed_args.repo or None,
                dry_run=parsed_args.dry_run,
            )
            return 0
    except Exception as exc:
        print(f"❌ PR Sage failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
