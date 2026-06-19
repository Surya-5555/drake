"""Reusable prompt template for Dell enterprise workflow discovery."""

from __future__ import annotations

import json

from src.core.models import EndpointContract
from ai_cluster.schemas.workflow import WorkflowMapping


class WorkflowPromptBuilder:
    """Build deterministic prompts for local workflow clustering."""

    def build(self, endpoints: list[EndpointContract]) -> str:
        """Build the workflow discovery prompt from validated endpoints."""

        endpoint_payload = [endpoint.model_dump(mode="json") for endpoint in endpoints]
        operation_ids = [endpoint.operation_id for endpoint in endpoints]

        schema_payload = WorkflowMapping.model_json_schema()

        return (
            "You are a Dell Enterprise Infrastructure Architect.\n"
            "You are a Senior Dell Enterprise Infrastructure Architect.\n\n"
            "You specialize in:\n"
            "- Dell iDRAC\n"
            "- Redfish APIs\n"
            "- OpenManage Enterprise\n"
            "- Enterprise Infrastructure Automation\n"
            "- Data Center Operations\n\n"
            "Your task is to analyze enterprise API endpoints and group them into "
            "logical workflow-level operations.\n\n"
            "Do not group solely by path similarity.\n"
            "Group endpoints by BUSINESS INTENT and OPERATIONAL WORKFLOW.\n"
            "Do NOT group solely by URL similarity.\n"
            "Do NOT group solely by resource names.\n"
            "Think like an experienced infrastructure operator.\n\n"
            "Example workflow names:\n"
            "- server_health_monitoring\n"
            "- server_power_management\n"
            "- firmware_management\n"
            "- inventory_reporting\n"
            "- storage_management\n"
            "- diagnostics\n"
            "- compliance_monitoring\n\n"
            "IMPORTANT:\n"
            "You are solving a CLUSTERING problem.\n"
            "You are NOT solving a TAGGING problem.\n\n"
            "Each endpoint belongs to ONE AND ONLY ONE workflow.\n"
            "If an endpoint could belong to multiple workflows, choose the SINGLE BEST workflow.\n\n"
            "CRITICAL CONSTRAINTS (MUST NOT BE VIOLATED):\n"
            "1. Every endpoint MUST appear in exactly one workflow.\n"
            "2. An endpoint may NEVER appear in multiple workflows.\n"
            "3. Duplicate endpoint assignments are forbidden.\n"
            "4. No endpoint may be omitted.\n"
            "5. No endpoint may be invented.\n"
            "6. Use only operationIds provided in the input.\n"
            "7. Never modify operationIds.\n"
            "8. Never create new operationIds.\n"
            "9. workflow_name must be snake_case.\n"
            "10. Workflow names must represent real enterprise operations.\n\n"
            "SELF-CHECK BEFORE RETURNING JSON:\n"
            "- Verify every input operationId appears exactly once.\n"
            "- Verify no operationId appears twice.\n"
            "- Verify no operationId is missing.\n"
            "- Verify no new operationIds were invented.\n"
            "- Verify every workflow contains at least one API.\n\n"
            "Required operationId checklist. These exact strings must each "
            "appear once and only once in underlying_api_calls:\n"
            f"{json.dumps(operation_ids, indent=2)}\n\n"
            "Return ONLY valid JSON.\n"
            "Return only JSON matching the supplied schema.\n"
            "Do NOT return markdown.\n"
            "Do NOT return explanations.\n"
            "Do NOT return conversational text.\n\n"
            "Contract B JSON Schema:\n"
            f"{json.dumps(schema_payload, indent=2)}\n\n"
            "Contract A Endpoints:\n"
            f"{json.dumps(endpoint_payload, indent=2)}"
        )
