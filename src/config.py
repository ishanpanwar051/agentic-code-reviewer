"""Configuration management for PR Sage using Pydantic Settings v2.

Interview Rationale (WHY):
- Structured & Validated Settings: Avoids silent runtime failures caused by missing environment variables,
  invalid repository strings, or unparseable timeouts.
- Fail-Fast Principle: Fails at startup before initiating expensive API calls or agent loops if configuration
  contracts are violated (e.g. missing GITHUB_TOKEN in production mode).
- Security Guardrails: Centralizes comment caps (MAX_COMMENTS_PER_PR, MAX_COMMENTS_PER_FILE) to prevent
  spamming pull requests or exceeding GitHub API rate limits.
"""

from __future__ import annotations

import fnmatch
import json
import re
from typing import Any
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_REGEX = re.compile(r"^[\w.-]+/[\w.-]+$")


class Settings(BaseSettings):
    """PR Sage application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
    )

    # Authentication & Repository
    GITHUB_TOKEN: str = Field(
        default="",
        description="GitHub Fine-grained Personal Access Token with Pull Requests Read & Write permissions.",
    )
    REPO: str = Field(
        default="",
        description="Target GitHub repository in 'owner/repo' format.",
    )

    # LLM Inference (Groq Cloud API)
    GROQ_API_KEY: str = Field(
        default="",
        description="Groq API key for cloud LLM inference (free tier available).",
    )
    GROQ_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Groq API base URL (OpenAI-compatible endpoint).",
    )
    MODEL_NAME: str = Field(
        default="llama-3.1-8b-instant",
        description="Groq model name for code review inference.",
    )

    # Guardrails: Noise & Rate Control
    MAX_COMMENTS_PER_PR: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum total comments to post per PR to prevent notification fatigue.",
    )
    MAX_COMMENTS_PER_FILE: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum comments posted on a single file.",
    )

    # Large File & Chunking Thresholds
    MAX_FILE_SIZE: int = Field(
        default=200_000,
        ge=1000,
        description="Maximum characters/bytes of a file diff before chunking or skipping.",
    )
    CHUNK_SIZE_LINES: int = Field(
        default=150,
        ge=20,
        le=1000,
        description="Target line window for code-aware diff chunking.",
    )
    CHUNK_OVERLAP_LINES: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Overlap lines between sequential chunks to preserve local context.",
    )

    # Diff Filter Patterns
    SKIP_PATHS: list[str] = Field(
        default_factory=lambda: [
            "package-lock.json",
            "yarn.lock",
            "poetry.lock",
            "Pipfile.lock",
            "*.min.js",
            "*.min.css",
            "*.lock",
            "*.png",
            "*.jpg",
            "*.jpeg",
            "*.svg",
            "*.gif",
            "*.ico",
            "*.woff",
            "*.woff2",
            "dist/*",
            "build/*",
            ".pytest_cache/*",
            "__pycache__/*",
        ],
        description="Glob patterns for files to ignore during PR review.",
    )

    # Operational Flags & Networking
    DRY_RUN: bool = Field(
        default=False,
        description="If True, performs analysis without posting reviews to GitHub API.",
    )
    DATABASE_PATH: str = Field(
        default="pr_sage.db",
        description="Path to SQLite persistence database file.",
    )
    OLLAMA_KEEP_ALIVE: str = Field(
        default="5m",
        description="Ollama model keep-alive duration (e.g. '5m', '0', '-1').",
    )
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins for API gateway.",
    )
    REQUEST_TIMEOUT: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="HTTP request timeout in seconds.",
    )
    MAX_RETRIES: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for transient API / network errors.",
    )

    @field_validator("SKIP_PATHS", mode="before")
    @classmethod
    def parse_skip_paths(cls, value: Any) -> list[str]:
        """Supports parsing SKIP_PATHS as a JSON array string or comma-separated string from env."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except Exception:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value]
        return value

    @field_validator("REPO")
    @classmethod
    def validate_repo_format(cls, value: str) -> str:
        """Validates REPO matches owner/repo format if non-empty."""
        value = value.strip()
        if value and not REPO_REGEX.match(value):
            raise ValueError(f"Invalid REPO format: '{value}'. Expected 'owner/repo' (e.g. 'octocat/Hello-World').")
        return value

    @model_validator(mode="after")
    def validate_auth_and_repo(self) -> Settings:
        """Enforces critical cross-field invariants for production execution."""
        if not self.DRY_RUN:
            if not self.GITHUB_TOKEN or not self.GITHUB_TOKEN.strip():
                raise ValueError("GITHUB_TOKEN is required when DRY_RUN=False. Set it in .env or environment.")
            if not self.REPO:
                raise ValueError("REPO is required when DRY_RUN=False. Set it in .env or environment (e.g. 'owner/repo').")
        return self


def should_skip_path(path: str, skip_patterns: list[str]) -> bool:
    """Evaluates whether a given file path matches any glob pattern in skip_patterns.

    Interview Rationale:
    - Normalizes Windows and POSIX separators to forward slashes.
    - Matches filename (e.g. package-lock.json) as well as path prefixes (e.g. dist/bundle.js).
    """
    normalized_path = path.replace("\\", "/").lstrip("/")
    basename = normalized_path.split("/")[-1]

    for pattern in skip_patterns:
        norm_pattern = pattern.replace("\\", "/").lstrip("/")
        if fnmatch.fnmatch(normalized_path, norm_pattern) or fnmatch.fnmatch(basename, norm_pattern):
            return True
        clean_dir = norm_pattern.rstrip("/*")
        if clean_dir and (normalized_path.startswith(f"{clean_dir}/") or f"/{clean_dir}/" in f"/{normalized_path}"):
            return True
    return False


# Singleton factory for global config
_settings_instance: Settings | None = None


def get_settings(**kwargs: Any) -> Settings:
    """Returns a singleton or customized instance of application Settings."""
    global _settings_instance
    if kwargs:
        return Settings(**kwargs)
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
