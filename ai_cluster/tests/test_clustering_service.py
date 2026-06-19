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


class RetryFakeOllamaService:
    def __init__(self) -> None:
        self.calls = 0

    def generate_workflow_mapping(self, prompt: str) -> dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            return {
                "workflows": [
                    {
                        "workflow_name": "server_health_monitoring",
                        "required_params": [],
                        "underlying_api_calls": ["getThermal"],
                    }
                ]
            }
        assert "Validation error" in prompt
        return {
            "workflows": [
                {
                    "workflow_name": "server_health_monitoring",
                    "required_params": [],
                    "underlying_api_calls": ["getThermal", "getPower"],
                }
            ]
        }


def test_clustering_service_generates_valid_contract_b() -> None:
    validation = WorkflowValidationService()
    endpoints = validation.validate_contract_a(
        {
            "spec_title": "Test",
            "spec_version": "1.0",
            "openapi_version": "3.0",
            "source_file": "test.json",
            "total_endpoints": 2,
            "endpoints": [
                {
                    "operation_id": "getThermal",
                    "method": "GET",
                    "url": "/redfish/v1/Thermal",
                    "required_params": [],
                },
                {
                    "operation_id": "getPower",
                    "method": "GET",
                    "url": "/redfish/v1/Power",
                    "required_params": [],
                },
            ]
        }
    )

    service = WorkflowClusteringService(
        ollama_service=FakeOllamaService(),  # type: ignore[arg-type]
        validation_service=validation,
        prompt_builder=WorkflowPromptBuilder(),
    )

    mapping = service.generate(endpoints)

    assert mapping.workflows[0].workflow_name == "server_health_monitoring"
    assert mapping.workflows[0].confidence == 0.95


def test_clustering_service_retries_after_invalid_mapping() -> None:
    validation = WorkflowValidationService()
    endpoints = validation.validate_contract_a(
        {
            "spec_title": "Test",
            "spec_version": "1.0",
            "openapi_version": "3.0",
            "source_file": "test.json",
            "total_endpoints": 2,
            "endpoints": [
                {
                    "operation_id": "getThermal",
                    "method": "GET",
                    "url": "/redfish/v1/Thermal",
                    "required_params": [],
                },
                {
                    "operation_id": "getPower",
                    "method": "GET",
                    "url": "/redfish/v1/Power",
                    "required_params": [],
                },
            ]
        }
    )
    fake_ollama = RetryFakeOllamaService()
    service = WorkflowClusteringService(
        ollama_service=fake_ollama,  # type: ignore[arg-type]
        validation_service=validation,
        prompt_builder=WorkflowPromptBuilder(),
        max_retries=1,
    )

    mapping = service.generate(endpoints)

    assert fake_ollama.calls == 2
    assert mapping.workflows[0].underlying_api_calls == ["getThermal", "getPower"]
