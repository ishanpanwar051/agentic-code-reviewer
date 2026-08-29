"""Tests for individual pipeline review stages and fault isolation."""

from unittest.mock import MagicMock
import pytest
from src.llm import LLMClient
from src.models import ReviewComment, StageResult
from src.stages import (
    ConsolidatedReviewResult,
    ErrorHandlingResult,
    ErrorHandlingStage,
    ReviewStage,
    SecurityResult,
    SecurityStage,
    UnderstandResult,
    UnderstandStage,
)


@pytest.fixture
def mock_llm() -> MagicMock:
    """Mock LLMClient instance."""
    return MagicMock(spec=LLMClient)


def test_understand_stage(mock_llm: MagicMock):
    """Verifies UnderstandStage builds context and emits structured summary notes."""
    mock_llm.complete_structured.return_value = UnderstandResult(
        summary="Adds JWT authentication middleware.",
        intent="Security enhancement",
        risk_areas=["token_decode", "secret_key_handling"],
    )

    stage = UnderstandStage()
    ctx = {
        "file_path": "src/auth.py",
        "lines": ["import jwt", "def decode(token): return jwt.decode(token)"],
        "added_line_numbers": [2],
        "start_line": 1,
    }

    result = stage.run(ctx, mock_llm)
    assert result.stage == "understand"
    assert len(result.findings) == 0
    assert "Adds JWT authentication" in result.notes
    assert "token_decode" in result.notes


def test_security_stage_enforces_category(mock_llm: MagicMock):
    """Verifies SecurityStage enforces category='security' and validates line numbers."""
    mock_llm.complete_structured.return_value = SecurityResult(
        findings=[
            ReviewComment(
                path="src/auth.py",
                line=2,
                severity="critical",
                category="bug",  # Incorrect category returned by LLM
                comment="Hardcoded JWT secret key.",
            )
        ],
        notes="High risk hardcoded secret detected.",
    )

    stage = SecurityStage()
    ctx = {
        "file_path": "src/auth.py",
        "lines": ["import jwt", "SECRET = '12345'"],
        "added_line_numbers": [2],
        "start_line": 1,
    }

    result = stage.run(ctx, mock_llm)
    assert result.stage == "security"
    assert len(result.findings) == 1
    assert result.findings[0].category == "security"
    assert result.findings[0].line == 2


def test_error_handling_stage(mock_llm: MagicMock):
    """Verifies ErrorHandlingStage audits silent swallows and exceptions."""
    mock_llm.complete_structured.return_value = ErrorHandlingResult(
        findings=[
            ReviewComment(
                path="src/service.py",
                line=5,
                severity="warning",
                category="clarity",
                comment="Bare except block silently swallows exceptions.",
            )
        ],
        notes="Silent failure present.",
    )

    stage = ErrorHandlingStage()
    ctx = {
        "file_path": "src/service.py",
        "lines": ["try:", "    do_work()", "except:", "    pass"],
        "added_line_numbers": [3, 4, 5],
        "start_line": 2,
    }

    result = stage.run(ctx, mock_llm)
    assert result.stage == "error_handling"
    assert len(result.findings) == 1
    assert result.findings[0].line == 5


def test_review_stage_deduplication(mock_llm: MagicMock):
    """Verifies ReviewStage merges prior findings and deduplicates comments."""
    prior_comment = ReviewComment(
        path="src/app.py",
        line=10,
        severity="critical",
        category="security",
        comment="SQL Injection in query string.",
    )

    # LLM returns duplicate + 1 new comment
    mock_llm.complete_structured.return_value = ConsolidatedReviewResult(
        comments=[
            ReviewComment(
                path="src/app.py",
                line=10,
                severity="critical",
                category="security",
                comment="SQL Injection in query string.",  # duplicate
            ),
            ReviewComment(
                path="src/app.py",
                line=12,
                severity="info",
                category="style",
                comment="Consider using f-strings for clarity.",
            ),
        ],
        summary="PR adds db query helper.",
    )

    stage = ReviewStage()
    ctx = {
        "file_path": "src/app.py",
        "lines": ["query = ...", "res = exec(query)", "print(res)"],
        "added_line_numbers": [10, 11, 12],
        "start_line": 10,
        "prior_findings": [prior_comment],
    }

    result = stage.run(ctx, mock_llm)
    assert result.stage == "review"
    # Deduplication should reduce 3 total to 2 unique comments
    assert len(result.findings) == 2
    lines = [f.line for f in result.findings]
    assert 10 in lines
    assert 12 in lines


def test_stage_graceful_skip_on_llm_failure(mock_llm: MagicMock):
    """Verifies stage does not crash the pipeline if LLM throws an exception."""
    mock_llm.complete_structured.side_effect = RuntimeError("Ollama connection timed out")

    stage = SecurityStage()
    ctx = {"file_path": "src/fault.py", "lines": ["x = 1"], "added_line_numbers": [1]}

    result = stage.run(ctx, mock_llm)
    assert result.stage == "security"
    assert result.findings == []
    assert "skipped: Ollama connection timed out" in result.notes
