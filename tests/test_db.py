"""Unit tests for PR Sage SQLite persistence layer (src/db.py)."""

from __future__ import annotations

from pathlib import Path
import pytest
from src.db import DatabaseManager
from src.models import ReviewComment, ReviewResult, ReviewTelemetry


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    """Fixture providing an isolated SQLite database instance."""
    db_file = tmp_path / "test_pr_sage.db"
    # Reset singleton instance
    DatabaseManager._instance = None
    db = DatabaseManager(str(db_file))
    return db


def test_db_schema_initialization(temp_db: DatabaseManager) -> None:
    """Verifies that SQLite tables are created with proper schemas and indices."""
    with temp_db._connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        assert "reviews" in tables
        assert "review_comments" in tables
        assert "feedback_events" in tables


def test_save_and_get_review(temp_db: DatabaseManager) -> None:
    """Verifies saving a ReviewResult and retrieving it with full comments."""
    comments = [
        ReviewComment(
            path="src/auth.py",
            line=42,
            severity="critical",
            category="security",
            cwe_id="CWE-89",
            comment="SQL injection risk in string formatting.",
            suggested_fix="cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
            confidence=0.95,
        ),
        ReviewComment(
            path="src/auth.py",
            line=55,
            severity="warning",
            category="reliability",
            cwe_id="CWE-391",
            comment="Bare except swallows all errors.",
            suggested_fix="except Exception as exc:\n    logger.error(exc)",
            confidence=0.88,
        ),
    ]
    telemetry = ReviewTelemetry(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=320,
        estimated_cost_usd=0.000015,
        model_name="llama-3.1-8b-instant",
    )
    result = ReviewResult(
        comments=comments,
        summary="Automated review detected 1 critical flaw.",
        telemetry=telemetry,
        patch_content="--- a/src/auth.py\n+++ b/src/auth.py\n",
    )

    review_id = temp_db.save_review(
        review_result=result,
        repo="octocat/Hello-World",
        pr_number=101,
        commit_sha="a1b2c3d4",
    )
    assert review_id > 0

    # Retrieve review
    record = temp_db.get_review(review_id)
    assert record is not None
    assert record["repo"] == "octocat/Hello-World"
    assert record["pr_number"] == 101
    assert record["commit_sha"] == "a1b2c3d4"
    assert record["critical_count"] == 1
    assert record["warning_count"] == 1
    assert record["info_count"] == 0
    assert len(record["comments"]) == 2
    assert record["comments"][0]["cwe_id"] == "CWE-89"


def test_list_recent_reviews(temp_db: DatabaseManager) -> None:
    """Verifies listing recent reviews with pagination."""
    for i in range(5):
        result = ReviewResult(
            comments=[],
            summary=f"Review summary {i}",
            telemetry=ReviewTelemetry(total_tokens=10 * i, latency_ms=100 * i, model_name="test-model"),
        )
        temp_db.save_review(result, repo="owner/repo", pr_number=i + 1)

    recent = temp_db.list_recent_reviews(limit=3)
    assert len(recent) == 3
    # Ordered by created_at DESC (pr_number 5, 4, 3)
    assert recent[0]["pr_number"] == 5
    assert recent[1]["pr_number"] == 4
    assert recent[2]["pr_number"] == 3


def test_record_feedback(temp_db: DatabaseManager) -> None:
    """Verifies recording developer feedback against a review and its comments."""
    result = ReviewResult(
        comments=[ReviewComment(path="test.py", line=1, severity="critical", category="security", comment="Bug")],
        summary="Summary",
    )
    review_id = temp_db.save_review(result, repo="owner/repo", pr_number=1)

    # Record feedback on overall review
    fb_id_1 = temp_db.record_feedback(review_id=review_id, action="thumbs_up", notes="Accurate review!")
    assert fb_id_1 > 0

    # Record feedback on specific comment
    fb_id_2 = temp_db.record_feedback(review_id=review_id, comment_id=1, action="applied", notes="Applied fix in git")
    assert fb_id_2 > 0


def test_get_statistics(temp_db: DatabaseManager) -> None:
    """Verifies aggregate telemetry and vulnerability metrics computation."""
    result1 = ReviewResult(
        comments=[
            ReviewComment(path="a.py", line=1, severity="critical", category="security", comment="C1"),
            ReviewComment(path="a.py", line=2, severity="warning", category="bug", comment="W1"),
        ],
        summary="Review 1",
        telemetry=ReviewTelemetry(latency_ms=200, total_tokens=100, estimated_cost_usd=0.001),
    )
    result2 = ReviewResult(
        comments=[ReviewComment(path="b.py", line=1, severity="info", category="style", comment="I1")],
        summary="Review 2",
        telemetry=ReviewTelemetry(latency_ms=400, total_tokens=200, estimated_cost_usd=0.002),
    )
    temp_db.save_review(result1, repo="owner/repo", pr_number=1)
    temp_db.save_review(result2, repo="owner/repo", pr_number=2)

    stats = temp_db.get_statistics()
    assert stats["total_reviews"] == 2
    assert stats["total_comments"] == 3
    assert stats["total_critical"] == 1
    assert stats["total_warning"] == 1
    assert stats["total_info"] == 1
    assert stats["avg_latency_ms"] == 300.0
    assert stats["total_tokens"] == 300
    assert pytest.approx(stats["total_cost_usd"], 0.0001) == 0.003
