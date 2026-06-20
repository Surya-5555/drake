"""Local Ollama service for structured workflow discovery responses."""

from __future__ import annotations

import json
import logging
from typing import Any

import instructor
import ollama

class WorkflowValidationError(Exception):
    pass

class Settings:
    OLLAMA_MODEL = "qwen2.5-coder:14b"
    OLLAMA_TIMEOUT = 30.0

settings = Settings()


class OllamaServiceError(RuntimeError):
    """Raised when local Ollama communication fails."""


class OllamaService:
    """Purpose: Communicate with local Ollama only.

    Responsibilities:
        Send prompts to phi3:mini, handle timeouts, and retrieve structured JSON.
    Inputs:
        Workflow discovery prompt strings.
    Outputs:
        Raw JSON objects that can validate as WorkflowMapping.
    """

    def __init__(
        self,
        model: str = settings.OLLAMA_MODEL,
        timeout: float = settings.OLLAMA_TIMEOUT,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize a local Ollama client."""
        self._model = model
        self._timeout = timeout
        self._logger = logger or logging.getLogger(__name__)
        self._client = ollama.Client(timeout=timeout)
        self._structured_output_library = instructor

    def generate_workflow_mapping(self, prompt: str) -> dict[str, Any]:
        """Request structured Contract B JSON from local Ollama."""
        self._logger.info("Sending clustering request to Ollama (Simulating instant failure)")
        raise OllamaServiceError("Fast fail for heuristics")

        content = self._extract_message_content(response)
        if not isinstance(content, str) or not content.strip():
            raise OllamaServiceError("Ollama returned an empty response")

        from src.ai_clustering.explain import is_explain_mode, explain_print
        if is_explain_mode():
            explain_print("RAW OLLAMA RESPONSE", content)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise WorkflowValidationError(f"Invalid JSON from Ollama: {exc}") from exc
        if not isinstance(parsed, dict):
            raise WorkflowValidationError("Ollama response must be a JSON object")
        return parsed

    def _extract_message_content(self, response: Any) -> str | None:
        """Extract assistant message content from supported Ollama responses."""
        if isinstance(response, dict):
            content = response.get("message", {}).get("content")
            return content if isinstance(content, str) else None

        message = getattr(response, "message", None)
        content = getattr(message, "content", None)
        return content if isinstance(content, str) else None
