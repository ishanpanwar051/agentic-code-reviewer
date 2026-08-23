"""Tests for PRSageAgent orchestrator and guardrails."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.agent import AgentState, PRSageAgent
from src.config import Settings
from src.github_client import GitHubClient
from src.llm import LLMClient
from src.models import ReviewComment
from src.stages import (
    ConsolidatedReviewResult,
    ErrorHandlingResult,
    SecurityResult,
    UnderstandResult,
)


@pytest.fixture
def mock_github() -> MagicMock:
    """Mock GitHubClient instance."""
    client = MagicMock(spec=GitHubClient)
    client.fetch_pr.return_value = {
        "title": "Add user authentication",
        "head": {"sha": "abc12345"},
    }
    client.fetch_pr_diff.return_value = """diff --git a/src/auth.py b/src/auth.py
index 0000000..1111111 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -0,0 +1,10 @@
+import os
+import jwt
+
+SECRET = "hardcoded_token_secret"
+
+def verify(token):
+    try:
+        return jwt.decode(token, SECRET)
+    except:
+        return None
"""
    return client


@pytest.fixture
def mock_llm() -> MagicMock:
    """Mock LLMClient returning structured stage outputs."""
    client = MagicMock(spec=LLMClient)

    def side_effect(prompt, output_model, system=None):
        if output_model == UnderstandResult:
            return UnderstandResult(
                summary="Auth module with token decode",
                intent="Authentication",
                risk_areas=["SECRET"],
            )
        elif output_model == SecurityResult:
            return SecurityResult(
                findings=[
                    ReviewComment(
                        path="src/auth.py",
                        line=4,
                        severity="critical",
                        category="security",
                        comment="Hardcoded secret token string.",
                    )
                ]
            )
        elif output_model == ErrorHandlingResult:
            return ErrorHandlingResult(
                findings=[
                    ReviewComment(
                        path="src/auth.py",
                        line=9,
                        severity="warning",
                        category="bug",
                        comment="Bare except swallows all errors.",
                    )
                ]
            )
        elif output_model == ConsolidatedReviewResult:
            return ConsolidatedReviewResult(
                comments=[
                    ReviewComment(
                        path="src/auth.py",
                        line=4,
                        severity="critical",
                        category="security",
                        comment="Hardcoded secret token string.",
                    ),
                    ReviewComment(
                        path="src/auth.py",
                        line=9,
                        severity="warning",
                        category="bug",
                        comment="Bare except swallows all errors.",
                    ),
                ],
                summary="PR introduces token authentication with security concerns.",
            )
        return output_model()

    client.complete_structured.side_effect = side_effect
    return client


def test_agent_state_validation():
    """Verifies state corruption detection in AgentState."""
    valid_state = AgentState(pr_number=1, owner="octocat", repo="repo")
    valid_state.validate_state()

    invalid_pr = AgentState(pr_number=0, owner="octocat", repo="repo")
    with pytest.raises(ValueError, match="Invalid PR number"):
        invalid_pr.validate_state()

    invalid_owner = AgentState(pr_number=1, owner="", repo="repo")
    with pytest.raises(ValueError, match="Invalid repository target"):
        invalid_owner.validate_state()


def test_agent_dry_run_execution(mock_github: MagicMock, mock_llm: MagicMock, tmp_path: Path, monkeypatch):
    """Verifies dry_run=True saves review_output.json and does not post to GitHub."""
    monkeypatch.chdir(tmp_path)
    settings = Settings(REPO="test-owner/test-repo", DRY_RUN=True)
    agent = PRSageAgent(settings=settings, github=mock_github, llm=mock_llm)

    result = agent.run(pr_number=42, dry_run=True)

    assert len(result.comments) == 2
    assert mock_github.post_review.called is False

    output_file = tmp_path / "review_output.json"
    assert output_file.exists()
    saved_data = json.loads(output_file.read_text())
    assert len(saved_data["comments"]) == 2
    assert saved_data["comments"][0]["severity"] == "critical"


def test_agent_post_review_execution(mock_github: MagicMock, mock_llm: MagicMock):
    """Verifies dry_run=False calls github.post_review with formatted comments."""
    settings = Settings(REPO="test-owner/test-repo", GITHUB_TOKEN="mock_pat_123", DRY_RUN=False)
    agent = PRSageAgent(settings=settings, github=mock_github, llm=mock_llm)

    result = agent.run(pr_number=42, dry_run=False)

    assert mock_github.post_review.called is True
    call_kwargs = mock_github.post_review.call_args.kwargs
    assert call_kwargs["owner"] == "test-owner"
    assert call_kwargs["repo"] == "test-repo"
    assert call_kwargs["pr_number"] == 42
    assert call_kwargs["commit_id"] == "abc12345"
    assert len(call_kwargs["comments"]) == 2
    assert "**[CRITICAL] [SECURITY]**" in call_kwargs["comments"][0]["body"]


def test_agent_guardrail_caps(mock_github: MagicMock):
    """Verifies MAX_COMMENTS_PER_FILE and MAX_COMMENTS_PER_PR caps."""
    settings = Settings(
        REPO="test-owner/test-repo",
        MAX_COMMENTS_PER_PR=3,
        MAX_COMMENTS_PER_FILE=2,
        DRY_RUN=True,
    )
    agent = PRSageAgent(settings=settings, github=mock_github)

    # 4 findings on a single file
    file_findings = [
        ReviewComment(path="a.py", line=1, severity="info", category="style", comment="style note"),
        ReviewComment(path="a.py", line=2, severity="warning", category="bug", comment="bug note"),
        ReviewComment(path="a.py", line=3, severity="critical", category="security", comment="security note"),
        ReviewComment(path="a.py", line=4, severity="info", category="clarity", comment="clarity note"),
    ]

    capped = agent._apply_file_guardrails(file_findings, "a.py")
    assert len(capped) == 2
    # Critical and warning must be prioritized over info
    assert capped[0].severity == "critical"
    assert capped[1].severity == "warning"

    # Global cap test (4 findings -> capped to 3)
    all_findings = [
        ReviewComment(path="a.py", line=1, severity="info", category="style", comment="1"),
        ReviewComment(path="b.py", line=2, severity="critical", category="security", comment="2"),
        ReviewComment(path="c.py", line=3, severity="warning", category="bug", comment="3"),
        ReviewComment(path="d.py", line=4, severity="critical", category="security", comment="4"),
    ]
    global_capped = agent._apply_global_guardrails(all_findings)
    assert len(global_capped) == 3
    severities = [f.severity for f in global_capped]
    assert severities == ["critical", "critical", "warning"]
