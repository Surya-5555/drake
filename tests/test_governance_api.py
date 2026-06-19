"""
Dell MCP — Pytest Suite for Governance API & SQLite Persistence
===============================================================

Validates database operations, graph-based community detection, and FastAPI routes.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from src.ai_clustering.graph_clustering import build_relationship_graph, detect_communities
from src.core.database import (
    DB_FILE,
    get_all_endpoints,
    get_db_connection,
    get_pipeline_statuses,
    get_workflows,
    init_db,
    log_audit_event,
    save_endpoints,
    save_workflows,
    set_pipeline_status,
)
from src.proxy.api import app


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Sets up an isolated database for unit tests and cleans up after."""
    # Ensure database is clean before running
    if DB_FILE.exists():
        try:
            os.remove(DB_FILE)
        except OSError:
            pass
            
    init_db()
    yield
    # Clean up test database
    if DB_FILE.exists():
        try:
            os.remove(DB_FILE)
        except OSError:
            pass


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
            "path": "/redfish/v1/Systems",
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
            "path": "/redfish/v1/Systems",
            "required_params": [],
        },
        {
            "operation_id": "PATCH_/redfish/v1/Systems",
            "method": "PATCH",
            "path": "/redfish/v1/Systems",
            "required_params": [],
        },
        {
            "operation_id": "GET_/redfish/v1/UpdateService",
            "method": "GET",
            "path": "/redfish/v1/UpdateService",
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
            "operation_id": "GET_/redfish/v1/Systems",
            "method": "GET",
            "path": "/redfish/v1/Systems",
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
    assert len(response.json()) == 1

    # 3. Test Update Workflow PATCH
    response = client.patch(
        "/api/v1/workflows/wf_1",
        json={
            "workflowName": "edited_systems_workflow",
            "generatedDescription": "Edited description",
        },
    )
    assert response.status_code == 200
    assert response.json()["workflowName"] == "edited_systems_workflow"

    # 4. Test Approve Workflow POST
    response = client.post("/api/v1/workflows/wf_1/approve")
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
