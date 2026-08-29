"""Tests for PR Sage configuration and settings validation."""

import pytest
from pydantic import ValidationError
from src.config import Settings, get_settings, should_skip_path


def test_default_settings():
    """Verifies default settings in DRY_RUN mode."""
    cfg = Settings(DRY_RUN=True)
    assert cfg.GROQ_BASE_URL == "https://api.groq.com/openai/v1"
    assert cfg.MODEL_NAME == "llama-3.1-8b-instant"
    assert cfg.MAX_COMMENTS_PER_PR == 10
    assert cfg.MAX_COMMENTS_PER_FILE == 5
    assert cfg.CHUNK_SIZE_LINES == 150
    assert cfg.CHUNK_OVERLAP_LINES == 20
    assert "package-lock.json" in cfg.SKIP_PATHS


def test_repo_validation_valid():
    """Verifies valid owner/repo strings."""
    cfg = Settings(REPO="ishan/pr-sage", GITHUB_TOKEN="dummy_pat_123", DRY_RUN=False)
    assert cfg.REPO == "ishan/pr-sage"


def test_repo_validation_invalid():
    """Verifies invalid REPO formats raise ValidationError."""
    with pytest.raises(ValidationError):
        Settings(REPO="invalid-repo-without-owner", DRY_RUN=True)

    with pytest.raises(ValidationError):
        Settings(REPO="owner/repo/extra", DRY_RUN=True)


def test_github_token_required_when_not_dry_run():
    """Verifies GITHUB_TOKEN and REPO are required when DRY_RUN=False."""
    with pytest.raises(ValidationError):
        Settings(DRY_RUN=False, GITHUB_TOKEN="", REPO="owner/repo")

    with pytest.raises(ValidationError):
        Settings(DRY_RUN=False, GITHUB_TOKEN="dummy_token", REPO="")


def test_skip_paths_parsing_from_json_string():
    """Verifies SKIP_PATHS correctly parses from JSON string."""
    cfg = Settings(SKIP_PATHS='["*.lock", "custom_build/*"]', DRY_RUN=True)
    assert cfg.SKIP_PATHS == ["*.lock", "custom_build/*"]


def test_should_skip_path():
    """Verifies glob path matching behavior."""
    patterns = ["package-lock.json", "*.min.js", "dist/*", "*.png"]

    assert should_skip_path("package-lock.json", patterns) is True
    assert should_skip_path("sub/dir/package-lock.json", patterns) is True
    assert should_skip_path("static/app.min.js", patterns) is True
    assert should_skip_path("dist/bundle.js", patterns) is True
    assert should_skip_path("dist/sub/deep/file.js", patterns) is True
    assert should_skip_path("images/hero.png", patterns) is True

    assert should_skip_path("src/main.py", patterns) is False
    assert should_skip_path("services/user_service.py", patterns) is False
