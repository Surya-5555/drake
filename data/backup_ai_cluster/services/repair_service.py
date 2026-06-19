"""Deterministic repair service for structurally invalid LLM workflow output."""

from __future__ import annotations

from src.core.models import EndpointContract
from ai_cluster.schemas.workflow import Workflow, WorkflowMapping


class WorkflowRepairService:
    """Purpose: Repair LLM workflow mappings after exhausted retries.

    Responsibilities:
        Remove duplicate API assignments, preserve first valid assignments,
        add missing endpoints by Dell operational intent, and recompute workflow
        required parameters.
    Inputs:
        A structurally valid WorkflowMapping and validated Contract A endpoints.
    Outputs:
        A repaired WorkflowMapping that must still pass strict validation.
    """

    def repair(
        self,
        mapping: WorkflowMapping,
        endpoints: list[EndpointContract],
    ) -> WorkflowMapping:
        """Repair duplicate and missing endpoint assignments deterministically."""
        endpoint_by_id = {endpoint.operation_id: endpoint for endpoint in endpoints}
        assigned: set[str] = set()
        repaired_workflows: dict[str, Workflow] = {}

        for workflow in mapping.workflows:
            unique_calls: list[str] = []
            for operation_id in workflow.underlying_api_calls:
                if operation_id in endpoint_by_id and operation_id not in assigned:
                    unique_calls.append(operation_id)
                    assigned.add(operation_id)
            if unique_calls:
                repaired_workflows[workflow.workflow_name] = workflow.model_copy(
                    update={
                        "underlying_api_calls": unique_calls,
                        "required_params": self._required_params(
                            unique_calls, endpoint_by_id
                        ),
                    }
                )

        for endpoint in endpoints:
            if endpoint.operation_id in assigned:
                continue
            workflow_name = self._infer_workflow_name(endpoint)
            existing = repaired_workflows.get(workflow_name)
            if existing is None:
                repaired_workflows[workflow_name] = Workflow(
                    workflow_name=workflow_name,
                    required_params=[p.name for p in endpoint.required_params],
                    underlying_api_calls=[endpoint.operation_id],
                    confidence=0.72,
                    reasoning=[
                        "deterministic repair after local LLM contract violation",
                        "classified by Dell operational intent from method and path",
                    ],
                )
            else:
                calls = [*existing.underlying_api_calls, endpoint.operation_id]
                repaired_workflows[workflow_name] = existing.model_copy(
                    update={
                        "underlying_api_calls": calls,
                        "required_params": self._required_params(calls, endpoint_by_id),
                    }
                )
            assigned.add(endpoint.operation_id)

        return WorkflowMapping(workflows=list(repaired_workflows.values()))

    def _infer_workflow_name(self, endpoint: EndpointContract) -> str:
        """Infer a Dell enterprise workflow name from endpoint intent."""
        signal = f"{endpoint.operation_id} {endpoint.method} {endpoint.url}".lower()
        if "updateservice" in signal or "firmware" in signal:
            return "firmware_management"
        if "reset" in signal or endpoint.method in {"PATCH", "PUT"}:
            return "server_power_management"
        if "accountservice" in signal or "account" in signal:
            return "account_access_management"
        if "storage" in signal or "volume" in signal or "drive" in signal:
            return "storage_management"
        if "log" in signal or "diagnostic" in signal:
            return "diagnostics"
        if "license" in signal or "compliance" in signal:
            return "compliance_monitoring"
        if "inventory" in signal or "collection" in signal:
            return "inventory_reporting"
        return "server_health_monitoring"

    def _required_params(
        self,
        operation_ids: list[str],
        endpoint_by_id: dict[str, EndpointContract],
    ) -> list[str]:
        """Return ordered union of required parameters for workflow execution."""
        params: list[str] = []
        seen: set[str] = set()
        for operation_id in operation_ids:
            for param in endpoint_by_id[operation_id].required_params:
                if param.name not in seen:
                    params.append(param.name)
                    seen.add(param.name)
        return params
