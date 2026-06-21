import os
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from src.core.database import (
    get_db_connection,
    init_db_sync,
    save_endpoints,
    save_workflows,
    async_session,
    EndpointStep
)
from src.proxy.api import app
from src.core.compatibility.orchestrator import WorkflowExecutionManager, CompatibilityPolicyViolation
from src.core.compatibility.models import CompatibilityStatus


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db_sync()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoints")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM audit_events")
        conn.execute("DELETE FROM compatibility_rules")
        conn.execute("DELETE FROM compatibility_dependencies")
        conn.execute("DELETE FROM device_inventory")
        conn.execute("DELETE FROM compatibility_reports")
        conn.commit()
    yield
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoints")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM audit_events")
        conn.execute("DELETE FROM compatibility_rules")
        conn.execute("DELETE FROM compatibility_dependencies")
        conn.execute("DELETE FROM device_inventory")
        conn.execute("DELETE FROM compatibility_reports")
        conn.commit()


@pytest.mark.asyncio
async def test_compatibility_governance_endpoints():
    # 1. Seed database with dummy workflow & rules
    dummy_eps = [
        {
            "operation_id": "GET_/redfish/v1/Systems/{ComputerSystemId}",
            "method": "GET",
            "url": "/redfish/v1/Systems/{ComputerSystemId}",
            "required_params": [],
            "community_id": "c1",
        }
    ]
    save_endpoints(dummy_eps)

    dummy_wfs = [
        {
            "id": "wf_test_1",
            "workflow_name": "test_workflow_1",
            "risk_level": "low",
            "cluster_size": 1,
            "confidence": 0.9,
            "generated_description": "Test workflow.",
            "community_id": "c1",
        }
    ]
    save_workflows(dummy_wfs)

    # Insert step
    async with async_session() as session:
        step = EndpointStep(
            workflow_id="wf_test_1",
            step_order=1,
            operation_id="GET_/redfish/v1/Systems/{ComputerSystemId}",
            method="GET",
            url="/redfish/v1/Systems/{ComputerSystemId}",
            required_params="[]",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        session.add(step)
        await session.commit()

    # Seed compatibility rules
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO compatibility_rules (id, rule_name, rule_type, domain, rule_version, effective_from, created_by, change_reason, rule_config)
            VALUES ('rule_bios_r750_min', 'Min BIOS', 'bios', 'BIOS', 1, ?, 'system', 'baseline', ?)
            """,
            (datetime.now(timezone.utc).isoformat(), '{"device_model": "PowerEdge R750", "min_bios_version": "2.12.0"}')
        )
        conn.commit()

    client = TestClient(app)

    # 2. Get Rules API
    response = client.get("/api/v1/compatibility/rules")
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) == 1
    assert rules[0]["id"] == "rule_bios_r750_min"

    # 3. Create Rule API
    response = client.post(
        "/api/v1/compatibility/rules",
        json={
            "id": "rule_hw_r640_unsupported",
            "rule_name": "Unsupported R640 Chassis",
            "rule_type": "hardware",
            "domain": "HARDWARE",
            "risk_score": 90,
            "rule_config": '{"supported_models": ["PowerEdge R750"]}'
        },
        headers={"X-API-Key": "default_dev_key"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "created"

    # 4. Get Compatibility Analysis API
    response = client.get("/api/v1/workflows/wf_test_1/compatibility?target_ip=192.168.0.120")
    assert response.status_code == 200
    comp_report = response.json()
    assert comp_report["workflowId"] == "wf_test_1"
    assert "compatibilityScore" in comp_report
    assert "findings" in comp_report


@pytest.mark.asyncio
async def test_runtime_policy_enforcement():
    # Setup test DB entries
    dummy_eps = [
        {
            "operation_id": "GET_/redfish/v1/Systems/{ComputerSystemId}",
            "method": "GET",
            "url": "/redfish/v1/Systems/{ComputerSystemId}",
            "required_params": [],
            "community_id": "c2",
        }
    ]
    save_endpoints(dummy_eps)

    dummy_wfs = [
        {
            "id": "wf_test_2",
            "workflow_name": "test_workflow_2",
            "risk_level": "medium",
            "cluster_size": 1,
            "confidence": 0.9,
            "generated_description": "Test workflow 2.",
            "community_id": "c2",
        }
    ]
    save_workflows(dummy_wfs)

    async with async_session() as session:
        step = EndpointStep(
            workflow_id="wf_test_2",
            step_order=1,
            operation_id="GET_/redfish/v1/Systems/{ComputerSystemId}",
            method="GET",
            url="/redfish/v1/Systems/{ComputerSystemId}",
            required_params="[]",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        session.add(step)
        await session.commit()

    # Seed a strict blocking BIOS rule (required BIOS 2.15.0)
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO compatibility_rules (id, rule_name, rule_type, domain, rule_version, effective_from, created_by, change_reason, rule_config)
            VALUES ('rule_bios_strict', 'Strict BIOS', 'bios', 'BIOS', 1, ?, 'system', 'baseline', ?)
            """,
            (datetime.now(timezone.utc).isoformat(), '{"device_model": "PowerEdge R750", "min_bios_version": "2.15.0"}')
        )
        conn.commit()

    # Setup mocks for executor requests
    with patch("src.proxy.executors.httpx_executor.httpx.AsyncClient") as MockClient:
        mock_client_instance = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": "Success"}
        mock_resp.text = '{"message": "Success"}'
        mock_client_instance.request = AsyncMock(return_value=mock_resp)

        mock_client_ctx = MagicMock()
        mock_client_ctx.__aenter__.return_value = mock_client_instance
        MockClient.return_value = mock_client_ctx

        # Configure environment variables
        os.environ["DELL_EXECUTOR_TYPE"] = "prism"
        os.environ["PRISM_URL"] = "http://localhost:4010"

        # 1. STRICT Policy + Violation (Target has BIOS 2.12.0, required is 2.15.0) -> Should raise CompatibilityPolicyViolation
        manager = WorkflowExecutionManager()
        
        # Mocking the live facts lookup to return R750 with BIOS 2.12.0
        from src.core.compatibility.models import DeviceFacts
        mock_facts = DeviceFacts(
            target_ip="192.168.0.120",
            device_model="PowerEdge R750",
            bios_version="2.12.0",
            last_scanned=datetime.now(timezone.utc)
        )
        
        with patch("src.core.compatibility.sources.RedfishFactsProvider.get_device_facts", AsyncMock(return_value=mock_facts)):
            with pytest.raises(CompatibilityPolicyViolation) as exc_info:
                await manager.execute_workflow_with_validation(
                    "test_workflow_2",
                    {"system_id": "sys123"},
                    target_ip="192.168.0.120",
                    policy="STRICT"
                )
            
            assert "STRICT Policy blocked execution" in str(exc_info.value)
            assert exc_info.value.report.status == CompatibilityStatus.BLOCK

            # 2. WARN_ONLY Policy + Violation -> Should execute but append warning metadata
            res_warn = await manager.execute_workflow_with_validation(
                "test_workflow_2",
                {"system_id": "sys123"},
                target_ip="192.168.0.120",
                policy="WARN_ONLY"
            )
            assert res_warn["compatibility_assessment"]["status"] == "BLOCK"
            assert len(res_warn["compatibility_assessment"]["violations"]) == 1

            # 3. DISABLED Policy -> Should execute without validation reports
            res_disabled = await manager.execute_workflow_with_validation(
                "test_workflow_2",
                {"system_id": "sys123"},
                target_ip="192.168.0.120",
                policy="DISABLED"
            )
            assert "compatibility_assessment" not in res_disabled


@pytest.mark.asyncio
async def test_explainability_endpoint():
    client = TestClient(app)
    dummy_eps = [
        {
            "operation_id": "GET_/redfish/v1/Systems/{ComputerSystemId}",
            "method": "GET",
            "url": "/redfish/v1/Systems/{ComputerSystemId}",
            "required_params": [],
            "community_id": "c_explain",
        }
    ]
    save_endpoints(dummy_eps)

    dummy_wfs = [
        {
            "id": "wf_explain_test",
            "workflow_name": "explain_test_wf",
            "risk_level": "low",
            "cluster_size": 1,
            "confidence": 0.9,
            "generated_description": "Explain test workflow.",
            "community_id": "c_explain",
        }
    ]
    save_workflows(dummy_wfs)

    async with async_session() as session:
        step = EndpointStep(
            workflow_id="wf_explain_test",
            step_order=1,
            operation_id="GET_/redfish/v1/Systems/{ComputerSystemId}",
            method="GET",
            url="/redfish/v1/Systems/{ComputerSystemId}",
            required_params="[]",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        session.add(step)
        await session.commit()

    response = client.get("/api/v1/workflows/wf_explain_test/explainability")
    assert response.status_code == 200
    report = response.json()
    assert report["workflow_id"] == "wf_explain_test"
    assert "blast_radius" in report
    assert "overall_risk_level" in report
    assert "dependency_graph_mermaid" in report
