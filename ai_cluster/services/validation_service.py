"""Validation service for Contract A and Contract B."""

from __future__ import annotations

from pydantic import ValidationError

from src.core.models import ContractA, EndpointContract
from ai_cluster.schemas.workflow import WorkflowMapping


class WorkflowValidationError(ValueError):
    """Raised when Contract A or Contract B fails workflow validation."""


class WorkflowValidationService:
    """Purpose: Validate input contracts, LLM responses, and Contract B output.

    Responsibilities:
        Detect duplicates, missing APIs, unknown APIs, empty contracts, and
        schema violations.
    Inputs:
        Raw Contract A JSON, WorkflowMapping objects, or raw LLM JSON objects.
    Outputs:
        Validated models or explicit validation exceptions.
    """

    def validate_contract_a(self, payload: object) -> list[EndpointContract]:
        """Validate raw Contract A JSON into endpoint models."""
        if not isinstance(payload, dict):
            raise WorkflowValidationError("Contract A must be a JSON object")

        try:
            contract_a = ContractA.model_validate(payload)
        except ValidationError as exc:
            raise WorkflowValidationError(f"Invalid Contract A: {exc}") from exc

        if not contract_a.endpoints:
            raise WorkflowValidationError("Contract A must not be empty")

        endpoints = contract_a.endpoints
        operation_ids = [endpoint.operation_id for endpoint in endpoints]
        duplicates = self._find_duplicates(operation_ids)
        if duplicates:
            raise WorkflowValidationError(
                f"Duplicate Contract A operationIds: {sorted(duplicates)}"
            )
        return endpoints

    def validate_llm_response(self, payload: object) -> WorkflowMapping:
        """Validate a raw LLM JSON response against Contract B schema."""
        try:
            mapping = WorkflowMapping.model_validate(payload)
        except ValidationError as exc:
            raise WorkflowValidationError(f"Invalid Contract B schema: {exc}") from exc
        return mapping

    def validate_contract_b(
        self, mapping: WorkflowMapping, endpoints: list[EndpointContract]
    ) -> WorkflowMapping:
        """Validate Contract B workflow membership against Contract A."""
        if not mapping.workflows:
            raise WorkflowValidationError("Contract B must contain workflows")

        expected_ids = {endpoint.operation_id for endpoint in endpoints}
        assigned_ids: list[str] = []
        for workflow in mapping.workflows:
            assigned_ids.extend(workflow.underlying_api_calls)

        duplicate_assignments = self._find_duplicates(assigned_ids)
        if duplicate_assignments:
            raise WorkflowValidationError(
                "APIs assigned to multiple workflows: "
                f"{sorted(duplicate_assignments)}"
            )

        assigned_set = set(assigned_ids)
        missing = expected_ids - assigned_set
        if missing:
            raise WorkflowValidationError(
                f"APIs missing from workflows: {sorted(missing)}"
            )

        unknown = assigned_set - expected_ids
        if unknown:
            raise WorkflowValidationError(
                f"Workflows reference unknown APIs: {sorted(unknown)}"
            )

        return mapping

    def _find_duplicates(self, values: list[str]) -> set[str]:
        """Return duplicate strings from a list."""
        seen: set[str] = set()
        duplicates: set[str] = set()
        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        return duplicates

