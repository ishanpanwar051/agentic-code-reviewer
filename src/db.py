"""Database persistence and audit management for PR Sage.

Provides SQLite persistence for:
- Repositories and Pull Requests
- Review execution records and telemetry
- Line-level review comments and suggested fixes
- Developer feedback events (applied, dismissed, helpful)
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import sqlite3
import threading
from typing import Any
from pydantic import BaseModel, Field
from src.models import ReviewComment, ReviewResult, ReviewTelemetry


logger = logging.getLogger("pr_sage.db")


class ReviewRecord(BaseModel):
    """Stored review record model."""

    id: int | None = None
    pr_number: int = 0
    repo: str = ""
    commit_sha: str = ""
    filename: str = ""
    status: str = "completed"
    summary: str = ""
    patch_content: str = ""
    comments_count: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    latency_ms: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model_name: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class StoredComment(BaseModel):
    """Stored review comment model."""

    id: int | None = None
    review_id: int
    file_path: str
    line_number: int
    severity: str
    category: str
    cwe_id: str | None = None
    comment: str
    suggested_fix: str | None = None
    confidence: float = 0.90
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class FeedbackRecord(BaseModel):
    """Stored developer feedback model."""

    id: int | None = None
    review_id: int
    comment_id: int | None = None
    action: str  # e.g., 'applied', 'dismissed', 'thumbs_up', 'thumbs_down'
    notes: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DatabaseManager:
    """Thread-safe SQLite database manager for PR Sage."""

    _instance: DatabaseManager | None = None
    _lock = threading.Lock()

    def __init__(self, db_path: str | Path = "pr_sage.db") -> None:
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: str | Path = "pr_sage.db") -> DatabaseManager:
        """Singleton instance accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path=db_path)
        return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a thread-local SQLite connection with WAL mode enabled."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.connection = conn
        return self._local.connection

    def _init_db(self) -> None:
        """Creates tables and indexes if they do not exist."""
        conn = self._get_connection()
        with conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_number INTEGER NOT NULL,
                repo TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                filename TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                summary TEXT NOT NULL,
                patch_content TEXT,
                comments_count INTEGER DEFAULT 0,
                critical_count INTEGER DEFAULT 0,
                warning_count INTEGER DEFAULT 0,
                info_count INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0.0,
                model_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS review_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                cwe_id TEXT,
                comment TEXT NOT NULL,
                suggested_fix TEXT,
                confidence REAL DEFAULT 0.90,
                created_at TEXT NOT NULL,
                FOREIGN KEY (review_id) REFERENCES reviews (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS feedback_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                comment_id INTEGER,
                action TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (review_id) REFERENCES reviews (id) ON DELETE CASCADE,
                FOREIGN KEY (comment_id) REFERENCES review_comments (id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_reviews_repo_pr ON reviews(repo, pr_number);
            CREATE INDEX IF NOT EXISTS idx_reviews_created ON reviews(created_at);
            CREATE INDEX IF NOT EXISTS idx_comments_review ON review_comments(review_id);
            CREATE INDEX IF NOT EXISTS idx_comments_cwe ON review_comments(cwe_id);
            """)

    def save_review(
        self,
        review_result: ReviewResult,
        repo: str = "local/repo",
        pr_number: int = 0,
        commit_sha: str = "HEAD",
        filename: str = "",
    ) -> int:
        """Persists a complete ReviewResult and returns the new review ID."""
        conn = self._get_connection()
        comments = review_result.comments
        telemetry = review_result.telemetry

        crit_count = sum(1 for c in comments if c.severity == "critical")
        warn_count = sum(1 for c in comments if c.severity == "warning")
        info_count = sum(1 for c in comments if c.severity == "info")

        with conn:
            cursor = conn.execute(
                """
                INSERT INTO reviews (
                    pr_number, repo, commit_sha, filename, status, summary,
                    patch_content, comments_count, critical_count, warning_count,
                    info_count, latency_ms, total_tokens, estimated_cost_usd,
                    model_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pr_number,
                    repo,
                    commit_sha,
                    filename or (comments[0].path if comments else "snippet.py"),
                    "completed",
                    review_result.summary,
                    review_result.patch_content,
                    len(comments),
                    crit_count,
                    warn_count,
                    info_count,
                    telemetry.latency_ms,
                    telemetry.total_tokens,
                    telemetry.estimated_cost_usd,
                    telemetry.model_name,
                    datetime.utcnow().isoformat(),
                ),
            )
            review_id = cursor.lastrowid

            for c in comments:
                conn.execute(
                    """
                    INSERT INTO review_comments (
                        review_id, file_path, line_number, severity, category,
                        cwe_id, comment, suggested_fix, confidence, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        review_id,
                        c.path,
                        c.line,
                        c.severity,
                        c.category,
                        c.cwe_id,
                        c.comment,
                        c.suggested_fix,
                        c.confidence,
                        datetime.utcnow().isoformat(),
                    ),
                )

        logger.info(f"Saved review #{review_id} for {repo} PR #{pr_number} with {len(comments)} findings.")
        return int(review_id) if review_id is not None else 0

    def get_review(self, review_id: int) -> dict[str, Any] | None:
        """Retrieves a review and its comments by ID."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
        review_row = cursor.fetchone()
        if not review_row:
            return None

        review_data = dict(review_row)
        cursor = conn.execute("SELECT * FROM review_comments WHERE review_id = ? ORDER BY line_number ASC", (review_id,))
        comments = [dict(row) for row in cursor.fetchall()]
        review_data["comments"] = comments
        return review_data

    def list_recent_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieves recent reviews sorted by newest first."""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT id, pr_number, repo, filename, comments_count, critical_count,
                   warning_count, info_count, latency_ms, total_tokens,
                   estimated_cost_usd, model_name, created_at
            FROM reviews
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def record_feedback(
        self,
        review_id: int,
        action: str,
        comment_id: int | None = None,
        notes: str = "",
    ) -> int:
        """Records developer interaction/feedback on a review or comment."""
        conn = self._get_connection()
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO feedback_events (review_id, comment_id, action, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (review_id, comment_id, action, notes, datetime.utcnow().isoformat()),
            )
            feedback_id = cursor.lastrowid
        return int(feedback_id) if feedback_id is not None else 0

    def get_statistics(self) -> dict[str, Any]:
        """Calculates global review metrics across all historical runs."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total_reviews,
                COALESCE(SUM(comments_count), 0) as total_comments,
                COALESCE(SUM(critical_count), 0) as total_critical,
                COALESCE(SUM(warning_count), 0) as total_warning,
                COALESCE(AVG(latency_ms), 0) as avg_latency_ms,
                COALESCE(SUM(estimated_cost_usd), 0.0) as total_cost_usd
            FROM reviews
        """)
        row = cursor.fetchone()
        return dict(row) if row else {}
