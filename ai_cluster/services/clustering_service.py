"""Workflow clustering orchestration service."""

from __future__ import annotations

import json
import logging

from ai_cluster.models.contract_a import ApiEndpoint
from ai_cluster.prompts.workflow_prompt import WorkflowPromptBuilder
from ai_cluster.schemas.workflow import WorkflowMapping
from ai_cluster.services.ollama_service import OllamaService
from ai_cluster.services.validation_service import WorkflowValidationService


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
    ) -> None:
        """Initialize clustering orchestration dependencies."""
        self._ollama_service = ollama_service
        self._validation_service = validation_service
        self._prompt_builder = prompt_builder or WorkflowPromptBuilder()
        self._logger = logger or logging.getLogger(__name__)

    def generate(self, endpoints: list[ApiEndpoint]) -> WorkflowMapping:
        """Generate a validated Contract B workflow mapping."""
        if not endpoints:
            raise ValueError("Cannot cluster an empty Contract A")

        prompt = self._prompt_builder.build(endpoints)

        self._logger.info(
            "Generating workflows from %s endpoints",
            len(endpoints),
        )

        raw_response = self._ollama_service.generate_workflow_mapping(prompt)

      