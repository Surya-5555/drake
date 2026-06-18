import pytest

from ai_cluster.schemas.workflow import WorkflowMapping
from ai_cluster.services.validation_service import (
    WorkflowValidationError,
    WorkflowValidationService,
)


def _contract_a() -> list[dict[str, object]]:
    return [
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


def test_validate_contract_a() -> None:
    endpoints = WorkflowValidationService().validate_contract_a(_contract_a())

    assert [endpoint.operationId for endpoint in endpoints] == [
        "getThermal",
        "getPower",
    ]


def test_validate_contract_a_rejects_duplicates() -> None:
    payload = _contract_a() + [_contract_a()[0]]

    with pytest.raises(WorkflowValidationError, match="Duplicate Contract A"):
        WorkflowValidationService().validate_contract_a(payload)


def test_validate_contract_b_accepts_complete_mapping() -> None:
    service = WorkflowValidationService()
    endpoints = service.validate_contract_a(_contract_a())
    mapping = WorkflowMapping.model_validate(
        {
            "workflows": [
                {
                    "workflow_name": "server_health_monitoring",
                    "required_params": [],
                    "underlying_api_calls": ["getThermal", "getPower"],
                }
            ]
        }
    )

    assert service.validate_contract_b(mapping, endpoints) == mapping


def test_validate_contract_b_rejects_duplicate_api_assignment() -> None:
    service = WorkflowValidationService()
    endpoints = service.validate_contract_a(_contract_a())
    mapping = WorkflowMapping.model_validate(
        {
            "workflows": [
                {
                    "workflow_name": "server_health_monitoring",
                    "required_params": [],
                    "underlying_api_calls": ["getThermal"],
                },
                {
                    "workflow_name": "inventory_reporting",
                    "required_params": [],
                    "underlying_api_calls": ["getThermal", "getPower"],
                },
            ]
        }
    )

    with pytest.raises(WorkflowValidationError, match="multiple workflows"):
        service.validate_contract_b(mapping, endpoints)


def test_validate_contract_b_rejects_missing_api() -> None:
    service = WorkflowValidationService()
    endpoints = service.validate_contract_a(_contract_a())
    mapping = WorkflowMapping.model_validate(
        {
            "workflows": [
                {
                    "workflow_name": "server_health_monitoring",
                    "required_params": [],
                    "underlying_api_calls": ["getThermal"],
                }
            ]
        }
    )

    with pytest.raises(WorkflowValidationError, match="missing"):
        service.validate_contract_b(mapping, endpoints)


def test_validate_llm_response_rejects_invalid_contract_b() -> None:
    with pytest.raises(WorkflowValidationError, match="Invalid Contract B"):
        WorkflowValidationService().validate_llm_response({"workflows": []})

