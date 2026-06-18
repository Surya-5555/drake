from ai_cluster.schemas.workflow import WorkflowMapping
from ai_cluster.services.repair_service import WorkflowRepairService
from ai_cluster.services.validation_service import WorkflowValidationService


def test_repair_service_removes_duplicates_and_adds_missing_apis() -> None:
    validation = WorkflowValidationService()
    endpoints = validation.validate_contract_a(
        [
            {
                "operationId": "GET_/redfish/v1",
                "method": "GET",
                "url": "/redfish/v1",
                "required_params": [],
            },
            {
                "operationId": "PATCH_/redfish/v1/Systems/{ComputerSystemId}",
                "method": "PATCH",
                "url": "/redfish/v1/Systems/{ComputerSystemId}",
                "required_params": ["ComputerSystemId"],
            },
            {
                "operationId": "POST_/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
                "method": "POST",
                "url": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
                "required_params": ["X-Correlation-ID"],
            },
        ]
    )
    invalid_mapping = WorkflowMapping.model_validate(
        {
            "workflows": [
                {
                    "workflow_name": "server_health_monitoring",
                    "required_params": [],
                    "underlying_api_calls": ["GET_/redfish/v1"],
                },
                {
                    "workflow_name": "inventory_reporting",
                    "required_params": [],
                    "underlying_api_calls": ["GET_/redfish/v1"],
                },
            ]
        }
    )

    repaired = WorkflowRepairService().repair(invalid_mapping, endpoints)

    validation.validate_contract_b(repaired, endpoints)
    all_calls = [
        operation_id
        for workflow in repaired.workflows
        for operation_id in workflow.underlying_api_calls
    ]
    assert sorted(all_calls) == sorted(endpoint.operationId for endpoint in endpoints)
    assert len(all_calls) == len(set(all_calls))
