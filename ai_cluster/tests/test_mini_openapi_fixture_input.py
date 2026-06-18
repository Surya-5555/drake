from pathlib import Path
from typing import Any

import yaml

from ai_cluster.schemas.workflow import WorkflowMapping
from ai_cluster.services.validation_service import WorkflowValidationService


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _contract_a_from_openapi(path: Path) -> list[dict[str, object]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    paths = document["paths"]
    endpoints: list[dict[str, object]] = []

    for url, path_item in paths.items():
        path_parameters = path_item.get("parameters", [])
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            parameters: list[dict[str, Any]] = [
                *path_parameters,
                *operation.get("parameters", []),
            ]
            required_params = [
                parameter["name"]
                for parameter in parameters
                if parameter.get("required") is True
            ]
            endpoints.append(
                {
                    "operationId": operation["operationId"],
                    "method": method.upper(),
                    "url": url,
                    "required_params": required_params,
                }
            )

    return endpoints


def test_mini_openapi_fixture_drives_contract_b_validation() -> None:
    fixture_path = Path("tests/fixtures/mini_openapi.yaml")
    validation = WorkflowValidationService()
    endpoints = validation.validate_contract_a(
        _contract_a_from_openapi(fixture_path)
    )
    mapping = WorkflowMapping.model_validate(
        {
            "workflows": [
                {
                    "workflow_name": "server_health_monitoring",
                    "required_params": ["ComputerSystemId"],
                    "underlying_api_calls": [
                        "GET_/redfish/v1",
                        "GET_/redfish/v1/Systems/{ComputerSystemId}",
                    ],
                },
                {
                    "workflow_name": "server_power_management",
                    "required_params": ["ComputerSystemId"],
                    "underlying_api_calls": [
                        "PATCH_/redfish/v1/Systems/{ComputerSystemId}",
                        "POST_/redfish/v1/Systems/{ComputerSystemId}/Actions/ComputerSystem.Reset",
                    ],
                },
                {
                    "workflow_name": "account_access_management",
                    "required_params": [],
                    "underlying_api_calls": [
                        "GET_/redfish/v1/AccountService/Accounts",
                        "POST_/redfish/v1/AccountService/Accounts",
                    ],
                },
                {
                    "workflow_name": "firmware_management",
                    "required_params": ["X-Correlation-ID"],
                    "underlying_api_calls": [
                        "POST_/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
                    ],
                },
            ]
        }
    )

    assert len(endpoints) == 7
    assert validation.validate_contract_b(mapping, endpoints) == mapping
