"""
GeminiProvider — concrete implementation of LLMProvider using google-genai SDK.

Key design decisions:
  - Structured output (response_schema) forces the model to return schema-shaped JSON.
  - temperature=0.0 for maximum determinism.
  - Retry with exponential backoff on transient failures.
  - Every failure raises LLMError with a machine-readable error_code.
  - The API key is read from the environment — never hard-coded.
"""

import os
import json
import time
import hashlib
from typing import Optional

from google import genai
from google.genai import types
from pydantic import ValidationError, TypeAdapter

from app.formalizer.llm.base import LLMProvider, LLMError
from app.formalizer.llm.prompts import AUTOFORMALIZER_SYSTEM_PROMPT
from app.schema.ast import ASTNode
from app.ontology.variables import registry
from app.config import settings


class GeminiProvider(LLMProvider):
    """
    Gemini-backed LLM provider.

    Responsibilities:
      1. Build the system prompt (registry context injected).
      2. Call Gemini with structured-output schema = ASTNode.
      3. Parse / validate the response into a typed ASTNode.
      4. Retry on transient errors; surface structured LLMError on failure.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self._model_name = model_name or settings.GEMINI_MODEL
        self._client = genai.Client()
        self._ast_adapter = TypeAdapter(ASTNode)

    # ── LLMProvider interface ──────────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "gemini"

    def extract_ast(self, criterion_text: str) -> ASTNode:
        """
        Call Gemini with structured output and return a validated ASTNode.
        Retries up to settings.GEMINI_MAX_RETRIES on transient failures.
        """
        system_prompt = AUTOFORMALIZER_SYSTEM_PROMPT.format(
            variable_registry_context=registry.to_prompt_context()
        )

        last_error: Optional[Exception] = None
        for attempt in range(1, settings.GEMINI_MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=criterion_text,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=ASTNode,
                        temperature=settings.GEMINI_TEMPERATURE,
                    ),
                )

                raw_text = response.text
                if not raw_text or not raw_text.strip():
                    raise LLMError(
                        "Gemini returned an empty response.",
                        error_code="LLM_EMPTY_RESPONSE",
                    )

                # Strip markdown fences if the model added them anyway
                text = raw_text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    text = text.rsplit("```", 1)[0].strip()

                try:
                    data = json.loads(text)
                except json.JSONDecodeError as e:
                    raise LLMError(
                        f"Gemini response is not valid JSON: {e}\nRaw: {raw_text[:300]}",
                        error_code="INVALID_LLM_OUTPUT",
                    )

                try:
                    return self._ast_adapter.validate_python(data)
                except ValidationError as e:
                    raise LLMError(
                        f"Gemini JSON does not match AST schema: {e}",
                        error_code="SCHEMA_VALIDATION_ERROR",
                    )

            except LLMError:
                raise  # Don't retry on schema/parse errors — they won't self-heal

            except Exception as exc:
                last_error = exc
                msg = str(exc).lower()
                if "rate" in msg or "quota" in msg:
                    # Rate limit — wait before retrying
                    wait = 2 ** attempt
                    time.sleep(wait)
                    continue
                if attempt < settings.GEMINI_MAX_RETRIES:
                    time.sleep(1)
                    continue
                break

        raise LLMError(
            f"Gemini call failed after {settings.GEMINI_MAX_RETRIES} attempts: {last_error}",
            error_code="LLM_API_ERROR",
        )
