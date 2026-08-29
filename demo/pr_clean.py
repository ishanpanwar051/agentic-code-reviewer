"""Demo File 1: Clean and Secure Implementation (Positive Control).

Expected Behavior:
- Stage 1 (Understand): Identifies secure user query and password hashing utility.
- Stage 2 (Security): No vulnerabilities found.
- Stage 3 (Error Handling): Proper specific exception handling and logging.
- Stage 4 (Review): 0 critical issues, approvals/clean summary.
"""

import hashlib
import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


class UserManager:
    """Manages user authentication and database queries safely."""

    def __init__(self, db_path: str = "users.db") -> None:
        self.db_path = db_path

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Fetches user details using parameterized queries to prevent SQL injection."""
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}")

        query = "SELECT id, username, email FROM users WHERE id = ?"
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, (user_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                return {"id": row[0], "username": row[1], "email": row[2]}
        except sqlite3.DatabaseError as exc:
            logger.error(f"Database query failed for user_id={user_id}: {exc}", exc_info=True)
            raise

    def hash_password(self, password: str, salt: bytes) -> str:
        """Securely hashes password using SHA-256 with per-user salt."""
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000).hex()
