from typing import Any

from ai_cluster.prompts.workflow_prompt import WorkflowPromptBuilder
from ai_cluster.services.clustering_service import WorkflowClusteringService
from ai_cluster.services.validation_service import WorkflowValidationService


class FakeOllamaService:
    def generate_workflow_mapping(self, prompt: str) -> dict[str, Any]:
        return {
            "workflows": [
                {
                    "workflow_name": "server_health_monitoring",
                    "required_params": [],
                    "underlying_api_calls": ["getThermal", "getPower"],
                    "confidence": 0.95,
                    "reasoning": ["shared monitoring intent"],
                }
            ]
        }


def test_clustering_service_generates_valid_contract_b() -> None:
    validation = WorkflowValidationService()
    endpoints = validation.validate_contract_a(
        [
            {
                "operationId": "getThermal",
                "method": "GET",
                "url": "/redfish/v1/Thermal",
                "required_params": [],
            },
            {
                "operationId": "getPower",
                "method": "GET",
                "url": "/redfish/v1/Power",
                "required_params": [],
            },
        ]
    )

    service = WorkflowClusteringService(
        ollama_service=FakeOllamaService(),  # type: ignore[arg-type]
        validation_service=validation,
        prompt_builder=WorkflowPromptBuilder(),
    )

    mapping = service.generate(endpoints)

    assert mapping.workflows[0].workflow_name == "server_health_monitoring"
    assert mapping.workflows[0].confidence == 0.95

