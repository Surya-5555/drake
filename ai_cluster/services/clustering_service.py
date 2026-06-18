"""Workflow clustering orchestration service."""

from __future__ import annotations

import logging

from ai_cluster.config.settings import settings
from ai_cluster.models.contract_a import ApiEndpoint
from ai_cluster.prompts.workflow_prompt import WorkflowPromptBuilder
from ai_cluster.schemas.workflow import WorkflowMapping
from ai_cluster.services.ollama_service import OllamaService
from ai_cluster.services.repair_service import WorkflowRepairService
from ai_cluster.services.validation_service import (
    WorkflowValidationError,
    WorkflowValidationService,
)


class WorkflowClusteringService:
    """Purpose: Generate Contract B from Contract A.

    Responsibilities:
        Prepare prompts, call the local LLM service, validate responses, and
        return the final workflow mapping.
    Inputs:
        Validated Contract A ApiEndpoint objects.
    Outputs:
        Validated WorkflowMapping object.
    """

    def __init__(
        self,
        ollama_service: OllamaService,
        validation_service: WorkflowValidationService,
        prompt_builder: WorkflowPromptBuilder | None = None,
        logger: logging.Logger | None = None,
        max_retries: int = settings.OLLAMA_MAX_RETRIES,
        repair_service: WorkflowRepairService | None = None,
    ) -> None:
        """Initialize clustering orchestration dependencies."""
        self._ollama_service = ollama_service
        self._validation_service = validation_service
        self._prompt_builder = prompt_builder or WorkflowPromptBuilder()
        self._logger = logger or logging.getLogger(__name__)
        self._max_retries = max_retries
        self._repair_service = repair_service or WorkflowRepairService()

    def generate(self, endpoints: list[ApiEndpoint]) -> WorkflowMapping:
        """Generate a validated Contract B workflow mapping."""
        if not endpoints:
            raise ValueError("Cannot cluster an empty Contract A")

        prompt = self._prompt_builder.build(endpoints)

        self._logger.info(
            "Generating workflows from %s endpoints",
            len(endpoints),
        )

        last_error: WorkflowValidationError | None = None
        last_mapping: WorkflowMapping | None = None
        for attempt in range(self._max_retries + 1):
            retry_prompt = self._build_retry_prompt(prompt, last_error, attempt)
            raw_response = self._ollama_service.generate_workflow_mapping(retry_prompt)
            try:
                mapping = self._validation_service.validate_llm_response(raw_response)
                last_mapping = mapping
                validated = self._validation_service.validate_contract_b(
                    mapping, endpoints
                )
                self._logger.info("Generated %s workflows", len(validated.workflows))
                return validated
            except WorkflowValidationError as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                self._logger.warning(
                    "Workflow validation failed on attempt %s: %s",
                    attempt + 1,
                    exc,
                )

        if last_mapping is not None:
            self._logger.warning(
                "Repairing workflow mapping after exhausted local LLM retries"
            )
            repaired = self._repair_service.repair(last_mapping, endpoints)
            validated = self._validation_service.validate_contract_b(
                repaired, endpoints
            )
            self._logger.info("Generated %s workflows", len(validated.workflows))
            return validated

        raise WorkflowValidationError("Workflow generation failed after retries")

    def _build_retry_prompt(
        self,
        base_prompt: str,
        last_error: WorkflowValidationError | None,
        attempt: int,
    ) -> str:
        """Append validation feedback after a failed LLM response."""
        if attempt == 0 or last_error is None:
            return base_prompt

        return (
            f"{base_prompt}\n\n"
            "Your previous JSON failed strict Contract B validation.\n"
            f"Validation error: {last_error}\n"
            "Regenerate the complete JSON. Every operationId from Contract A "
            "must appear exactly once in underlying_api_calls."
        )
