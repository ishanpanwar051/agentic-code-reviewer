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
