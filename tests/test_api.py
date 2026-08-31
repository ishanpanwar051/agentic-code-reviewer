"""Unit tests for PR Sage FastAPI REST API and Webhook Gateway."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from src.api import app


client = TestClient(app)


def test_health_check() -> None:
    """Tests the /health endpoint returns healthy status and service version."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "pr-sage-agentic-reviewer"
    assert "version" in data


def test_review_code_endpoint() -> None:
    """Tests the /api/v1/review/code endpoint reviews code and returns structured findings."""
    payload = {
        "code": "def divide(a, b):\n    return a / 0\n",
        "filename": "math_ops.py",
        "model": "hybrid-ast",
        "confidence_threshold": 0.50,
    }
    response = client.post("/api/v1/review/code", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "comments" in data
    assert "telemetry" in data
    assert "patch_content" in data


def test_github_webhook_ping() -> None:
    """Tests the /api/v1/webhooks/github endpoint handles ping events."""
    headers = {
        "X-GitHub-Event": "ping",
    }
    response = client.post("/api/v1/webhooks/github", headers=headers, json={"zen": "Practicality beats purity."})
    assert response.status_code == 200
    data = response.json()
    assert "pong" in data.get("message", "")


def test_reviews_history_and_feedback_endpoints() -> None:
    """Tests /api/v1/reviews history querying and /feedback submission."""
    # 1. Trigger a review snippet
    payload = {
        "code": "import os\nSECRET = 'hardcoded_token'\n",
        "filename": "auth.py",
        "confidence_threshold": 0.50,
    }
    rev_resp = client.post("/api/v1/review/code", json=payload)
    assert rev_resp.status_code == 200

    # 2. List reviews
    list_resp = client.get("/api/v1/reviews?limit=10")
    assert list_resp.status_code == 200
    reviews = list_resp.json()
    assert len(reviews) >= 1
    target_id = reviews[0]["id"]

    # 3. Get single review
    detail_resp = client.get(f"/api/v1/reviews/{target_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == target_id

    # 4. Submit feedback
    fb_resp = client.post(
        f"/api/v1/reviews/{target_id}/feedback",
        json={"action": "applied", "notes": "Merged in git"},
    )
    assert fb_resp.status_code == 200
    assert fb_resp.json()["status"] == "recorded"


def test_github_webhook_hmac_enforcement(monkeypatch) -> None:
    """Tests that webhook rejects payloads with invalid or missing HMAC when secret is configured."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test_secret_123")

    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": "sha256=invalid_hash",
    }
    response = client.post(
        "/api/v1/webhooks/github",
        headers=headers,
        json={"action": "opened", "pull_request": {"number": 1}},
    )
    assert response.status_code == 401

