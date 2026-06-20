"""
Dell MCP — Pytest Suite for Governance API & SQLite Persistence
===============================================================

Validates database operations, graph-based community detection, and FastAPI routes.
"""

from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient

from src.ai_clustering.graph_clustering import (
    build_relationship_graph,
    detect_communities,
)
from src.core.database import (
    get_all_endpoints,
    get_db_connection,
    get_pipeline_statuses,
    get_workflows,
    init_db_sync,
    save_endpoints,
    save_workflows,
    set_pipeline_status,
)
from src.proxy.api import app


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Sets up an isolated database for unit tests and cleans up after."""
    init_db_sync()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoints")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM audit_events")
        conn.execute("UPDATE pipeline_status SET status = 'idle'")
        conn.commit()
    yield
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoints")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM audit_events")
        conn.execute("UPDATE pipeline_status SET status = 'idle'")
        conn.commit()


def test_database_init() -> None:
    """Validate database tables are initialized with default stages."""
    statuses = get_pipeline_statuses()
    assert "ingestionStatus" in statuses
    assert "graphStatus" in statuses
    assert statuses["ingestionStatus"] == "idle"


def test_endpoint_and_workflow_persistence() -> None:
    """Validate endpoints and workflow structures can be saved and retrieved."""
    # Save a dummy endpoint
    dummy_eps = [
        {
            "operation_id": "GET_/redfish/v1/Systems",
            "method": "GET",
            "url": "/redfish/v1/Systems",
            "required_params": [],
            "community_id": "1",
        }
    ]
    save_endpoints(dummy_eps)

    eps = get_all_endpoints()
    assert len(eps) == 1
    assert eps[0]["operation_id"] == "GET_/redfish/v1/Systems"

    # Save a dummy workflow cluster
    dummy_wfs = [
        {
            "id": "wf_1",
            "workflow_name": "systems_query_workflow",
            "risk_level": "low",
            "cluster_size": 1,
            "confidence": 0.9,
            "generated_description": "Query Dell systems details.",
            "community_id": "1",
        }
    ]
    save_workflows(dummy_wfs)

    wfs = get_workflows()
    assert len(wfs) == 1
    assert wfs[0]["workflowName"] == "systems_query_workflow"
    assert wfs[0]["clusterSize"] == 1
    assert len(wfs[0]["underlyingEndpoints"]) == 1
    assert wfs[0]["underlyingEndpoints"][0]["operationId"] == "GET_/redfish/v1/Systems"


def test_relationship_graph_and_communities() -> None:
    """Validate NetworkX graph construction and community detection."""
    endpoints = [
        {
            "operation_id": "GET_/redfish/v1/Systems",
            "method": "GET",
            "url": "/redfish/v1/Systems",
            "required_params": [],
        },
        {
            "operation_id": "PATCH_/redfish/v1/Systems",
            "method": "PATCH",
            "url": "/redfish/v1/Systems",
            "required_params": [],
        },
        {
            "operation_id": "GET_/redfish/v1/UpdateService",
            "method": "GET",
            "url": "/redfish/v1/UpdateService",
            "required_params": [],
        },
    ]

    G = build_relationship_graph(endpoints)
    assert G.number_of_nodes() == 3
    # Systems GET and Systems PATCH should be connected (same path)
    assert G.has_edge("GET_/redfish/v1/Systems", "PATCH_/redfish/v1/Systems")
    # Systems and UpdateService should not be connected
    assert not G.has_edge("GET_/redfish/v1/Systems", "GET_/redfish/v1/UpdateService")

    communities = detect_communities(G)
    assert len(communities) >= 2


def test_fastapi_endpoints() -> None:
    """Validate FastAPI REST responses using TestClient."""
    # Seed DB first
    dummy_eps = [
        {
            "operation_id": "POST_/redfish/v1/Systems",
            "method": "POST",
            "url": "/redfish/v1/Systems",
            "required_params": [],
            "community_id": "1",
        }
    ]
    dummy_wfs = [
        {
            "id": "wf_1",
            "workflow_name": "systems_query_workflow",
            "risk_level": "low",
            "cluster_size": 1,
            "confidence": 0.9,
            "generated_description": "Query Dell systems details.",
            "community_id": "1",
        }
    ]
    save_endpoints(dummy_eps)
    save_workflows(dummy_wfs)
    set_pipeline_status("ingestionStatus", "complete")

    client = TestClient(app)

    # 1. Test Overview API
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["endpointCount"] == 1
    assert data["workflowCount"] == 1
    assert data["pendingReviewCount"] == 1
    assert data["ingestionStatus"] == "complete"

    # 2. Test Pending Workflows
    response = client.get("/api/v1/workflows/pending")
    assert response.status_code == 200
    pending_wfs = response.json()
    assert len(pending_wfs) == 1
    assert "underlyingEndpoints" in pending_wfs[0]
    assert len(pending_wfs[0]["underlyingEndpoints"]) == 1
    assert pending_wfs[0]["underlyingEndpoints"][0]["operationId"] == "POST_/redfish/v1/Systems"

    # 3. Test Update Workflow PATCH
    response = client.patch(
        "/api/v1/workflows/wf_1",
        json={
            "workflowName": "edited_systems_workflow",
            "generatedDescription": "Edited description",
        },
        headers={"X-API-Key": "default_dev_key"},
    )
    assert response.status_code == 200
    updated_wf = response.json()
    assert updated_wf["workflowName"] == "edited_systems_workflow"
    assert "underlyingEndpoints" in updated_wf
    assert len(updated_wf["underlyingEndpoints"]) == 1

    # 4. Test Approve Workflow POST
    response = client.post(
        "/api/v1/workflows/wf_1/approve",
        headers={"X-API-Key": "default_dev_key"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    # Ensure overview reports 0 pending and 1 registered
    response = client.get("/api/v1/overview")
    assert response.json()["pendingReviewCount"] == 0
    assert response.json()["registeredWorkflowCount"] == 1

    # 5. Test Metrics
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert metrics["rawEndpointCount"] == 1
    assert metrics["approvedCount"] == 1
    assert metrics["pendingCount"] == 0

    # 6. Test Graph
    response = client.get("/api/v1/graph")
    assert response.status_code == 200
    graph = response.json()
    assert len(graph["nodes"]) == 1
    assert len(graph["communities"]) == 1

    # 7. Test Audit log
    response = client.get("/api/v1/audit/events")
    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 2  # generated + approved


def test_prometheus_metrics_endpoint() -> None:
    """Validate Prometheus scraping metrics endpoint."""
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "dell_mcp_endpoints_total" in text
    assert "dell_mcp_workflows_total" in text
    assert "dell_mcp_workflows_approved_total" in text


def test_export_workflow_ansible() -> None:
    """Validate Ansible Playbook export endpoint for a workflow."""
    from src.core.database import save_workflows, get_db_connection
    dummy_wfs = [
        {
            "id": "wf_ansible_test",
            "workflow_name": "ansible_test_workflow",
            "risk_level": "medium",
            "cluster_size": 1,
            "confidence": 0.95,
            "generated_description": "Ansible test workflow description.",
            "community_id": "c_ansible",
        }
    ]
    save_workflows(dummy_wfs)
    
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            ("wf_ansible_test", 1, "test_op", "GET", "/redfish/v1/Systems", "[]"),
        )
        conn.commit()

    client = TestClient(app)
    response = client.get("/api/v1/workflows/wf_ansible_test/export/ansible")
    assert response.status_code == 200
    yaml_text = response.text
    assert "ansible.builtin.uri" in yaml_text
    assert "/redfish/v1/Systems" in yaml_text
    assert "idrac_servers" in yaml_text
