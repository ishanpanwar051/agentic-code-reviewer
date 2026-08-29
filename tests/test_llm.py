"""Tests for LLMClient structured output parsing and retry repair mechanisms."""

import httpx
import pytest
import respx
from pydantic import BaseModel, Field
from src.llm import LLMClient, StructuredOutputError


class MockOutputSchema(BaseModel):
    summary: str
    count: int = Field(default=1)
    tags: list[str] = Field(default_factory=list)


@respx.mock
def test_complete_success_with_keep_alive():
    """Verifies complete sends keep_alive=0 for 8GB RAM conservation."""
    route = respx.post("http://localhost:11434/api/chat").respond(
        status_code=200,
        json={"message": {"content": "Hello World"}},
    )

    client = LLMClient(base_url="http://localhost:11434")
    response = client.complete("Hi", system="You are helper")

    assert response == "Hello World"
    assert route.called
    req_json = route.calls.last.request.read().decode()
    assert '"keep_alive": 0' in req_json


@respx.mock
def test_complete_retry_on_server_error(monkeypatch):
    """Verifies retry backoff on transient HTTP 500 server error."""
    monkeypatch.setattr("time.sleep", lambda s: None)

    route = respx.post("http://localhost:11434/api/chat")
    route.side_effect = [
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(200, json={"message": {"content": "Recovered"}}),
    ]

    client = LLMClient(base_url="http://localhost:11434", max_retries=2)
    response = client.complete("Test retry")
    assert response == "Recovered"
    assert route.call_count == 2


@respx.mock
def test_complete_structured_clean_json():
    """Verifies structured output parsing with direct valid JSON."""
    respx.post("http://localhost:11434/api/chat").respond(
        status_code=200,
        json={"message": {"content": '{"summary": "Auth module updated", "count": 3, "tags": ["security"]}'}},
    )

    client = LLMClient(base_url="http://localhost:11434")
    result = client.complete_structured("Review this", MockOutputSchema)

    assert isinstance(result, MockOutputSchema)
    assert result.summary == "Auth module updated"
    assert result.count == 3
    assert result.tags == ["security"]


@respx.mock
def test_complete_structured_strips_markdown_fences():
    """Verifies markdown code fences ```json ... ``` are cleanly stripped."""
    raw_markdown = """```json
{
  "summary": "Cleaned markdown",
  "count": 5,
  "tags": ["refactor"]
}
```"""
    respx.post("http://localhost:11434/api/chat").respond(
        status_code=200,
        json={"message": {"content": raw_markdown}},
    )

    client = LLMClient(base_url="http://localhost:11434")
    result = client.complete_structured("Review this", MockOutputSchema)

    assert result.summary == "Cleaned markdown"
    assert result.count == 5


@respx.mock
def test_complete_structured_repair_retry_success(monkeypatch):
    """Verifies that invalid JSON on attempt 1 triggers repair prompt and succeeds on attempt 2."""
    monkeypatch.setattr("time.sleep", lambda s: None)

    route = respx.post("http://localhost:11434/api/chat")
    route.side_effect = [
        httpx.Response(200, json={"message": {"content": "Invalid JSON without braces"}}),
        httpx.Response(200, json={"message": {"content": '{"summary": "Fixed JSON", "count": 1, "tags": []}'}}),
    ]

    client = LLMClient(base_url="http://localhost:11434", max_retries=2)
    result = client.complete_structured("Review this", MockOutputSchema)

    assert result.summary == "Fixed JSON"
    assert route.call_count == 2


@respx.mock
def test_complete_structured_exhaustion_raises_error(monkeypatch):
    """Verifies persistent malformed JSON raises StructuredOutputError."""
    monkeypatch.setattr("time.sleep", lambda s: None)

    respx.post("http://localhost:11434/api/chat").respond(
        status_code=200,
        json={"message": {"content": "Not JSON at all"}},
    )

    client = LLMClient(base_url="http://localhost:11434", max_retries=1)
    with pytest.raises(StructuredOutputError):
        client.complete_structured("Review this", MockOutputSchema)
