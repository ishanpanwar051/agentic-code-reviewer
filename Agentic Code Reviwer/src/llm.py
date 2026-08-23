"""Local LLM interaction client for Ollama with structured output enforcement.

Interview Rationale (WHY):
- Strict JSON & Pydantic Schema Injection: Small local models (llama3.2:3b) can produce markdown chatter.
  We inject the exact JSON schema and few-shot formatting instructions into the prompt.
- Self-Correction / Repair Retry: If initial JSON decoding or Pydantic validation fails, we feed the exact validation
  error back to the model for a surgical 1-shot repair retry rather than crashing.
- 8GB RAM Optimization (keep_alive=0): Unloads model weights from memory immediately after inference, preventing
  RAM starvation on resource-constrained development machines.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, TypeVar
import httpx
from pydantic import BaseModel, ValidationError


logger = logging.getLogger("pr_sage.llm")

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """Raised when the LLM repeatedly fails to produce valid structured JSON adhering to the schema."""


class LLMClient:
    """Ollama API client with structured output extraction and memory management."""

    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.2,
        timeout: float = 120.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self._client = client or httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        """Closes the HTTP client session."""
        self._client.close()

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        format: dict[str, Any] | str | None = None,
    ) -> str:
        """Sends a completion request to Ollama with keep_alive=0 for RAM conservation."""
        url = f"{self.base_url}/api/chat"

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": self.temperature,
            },
            "stream": False,
            "keep_alive": 0,  # Unload immediately after inference (8GB RAM rule)
        }
        if format is not None:
            payload["format"] = format

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.post(url, json=payload)
                if response.is_success:
                    data = response.json()
                    return data.get("message", {}).get("content", "").strip()  # type: ignore[no-any-return]
                response.raise_for_status()
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    backoff = (2**attempt) * 1.0
                    logger.warning(
                        f"Ollama call failed on attempt {attempt + 1}/{self.max_retries}: {exc}. Retrying in {backoff:.1f}s."
                    )
                    time.sleep(backoff)
                    continue
                break

        raise RuntimeError(f"Ollama API request failed after {self.max_retries} attempts: {last_error}")

    def complete_structured(
        self,
        prompt: str,
        output_model: type[T],
        system: str | None = None,
    ) -> T:
        """Enforces Pydantic structured output from Ollama with repair retries."""
        schema_json = json.dumps(output_model.model_json_schema(), indent=2)
        format_instruction = (
            f"\n\nCRITICAL INSTRUCTION: You must respond ONLY with a single valid JSON object that strictly adheres "
            f"to the following JSON schema. Do not enclose in markdown fences, do not add explanation, do not include comments.\n\n"
            f"JSON Schema:\n{schema_json}"
        )

        augmented_prompt = prompt + format_instruction
        current_prompt = augmented_prompt
        last_validation_error: str = ""

        for attempt in range(self.max_retries + 1):
            raw_response = self.complete(
                current_prompt,
                system=system,
                format=output_model.model_json_schema(),
            )
            cleaned_json_str = self._extract_json_block(raw_response)

            try:
                parsed_dict = json.loads(cleaned_json_str)
                validated_model = output_model.model_validate(parsed_dict)
                return validated_model
            except (json.JSONDecodeError, ValidationError) as exc:
                last_validation_error = str(exc)
                logger.warning(
                    f"Structured output validation failed (attempt {attempt + 1}/{self.max_retries + 1}): {exc}"
                )

                if attempt < self.max_retries:
                    # Repair retry prompt feeding the exact validation error back to LLM
                    current_prompt = (
                        f"{augmented_prompt}\n\n"
                        f"ATTENTION: Your previous response failed with error:\n{last_validation_error}\n"
                        f"Previous invalid output:\n{raw_response}\n\n"
                        f"Please provide ONLY the corrected, valid JSON object now."
                    )

        raise StructuredOutputError(
            f"Failed to parse structured output for {output_model.__name__} after {self.max_retries + 1} attempts. Error: {last_validation_error}"
        )

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """Extracts JSON substring, stripping markdown fences and leading/trailing chatter."""
        text = text.strip()

        # Strip markdown ```json ... ``` code fences
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1).strip()

        # Find first { or [ and last } or ]
        first_brace = text.find("{")
        last_brace = text.rfind("}")

        first_bracket = text.find("[")
        last_bracket = text.rfind("]")

        start = -1
        end = -1

        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            start = first_brace
            end = last_brace + 1 if last_brace != -1 else len(text)
        elif first_bracket != -1:
            start = first_bracket
            end = last_bracket + 1 if last_bracket != -1 else len(text)

        if start != -1 and end != -1 and end > start:
            return text[start:end].strip()

        return text
