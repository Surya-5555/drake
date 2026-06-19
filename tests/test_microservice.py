import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from src.core.database import async_session, Workflow, EndpointStep
from src.proxy.server import app, mcp


def test_workflow_lifecycle_and_reload():
    """
    Integration test validating the full workflow status lifecycle (pending -> approved/rejected),
    the SQLite ORM persistence layer, the /reload hot-reload handler, and FastMCP tool registration.
    """
    with TestClient(app) as client:
        # Helper to run async db seeding
        async def seed_pending_workflow():
            async with async_session() as session:
                # Clean up existing test workflows for isolation
                await session.execute(
                    delete(Workflow).where(Workflow.id.in_(["test_wf_1", "test_wf_2"]))
                )
                
                # Insert first workflow as pending
                wf1 = Workflow(
                    id="test_wf_1",
                    name="test_workflow_one",
                    description="A test workflow description",
                    risk_level="low",
                    status="pending"
                )
                step1 = EndpointStep(
                    method="GET",
                    path="/redfish/v1/Systems/{ComputerSystemId}"
                )
                wf1.steps.append(step1)
                
                # Insert second workflow as pending
                wf2 = Workflow(
                    id="test_wf_2",
                    name="test_workflow_two",
                    description="Second test workflow",
                    risk_level="high",
                    status="pending"
                )
                
                session.add_all([wf1, wf2])
                await session.commit()

        asyncio.run(seed_pending_workflow())

        # 1. Verify GET /workflows/pending returns our seeded workflows
        response = client.get("/workflows/pending")
        assert response.status_code == 200
        pending_list = response.json()
        assert len(pending_list) >= 2
        assert any(wf["id"] == "test_wf_1" for wf in pending_list)
        assert any(wf["id"] == "test_wf_2" for wf in pending_list)

        # 2. Approve test_wf_1 via REST endpoint
        response = client.post("/workflows/test_wf_1/approve")
        assert response.status_code == 200
        assert response.json() == {"message": "Workflow test_wf_1 approved successfully"}

        # 3. Reject test_wf_2 via REST endpoint
        response = client.post("/workflows/test_wf_2/reject")
        assert response.status_code == 200
        assert response.json() == {"message": "Workflow test_wf_2 rejected successfully"}

        # Verify statuses updated correctly in SQLite
        async def verify_database_states():
            async with async_session() as session:
                wf1 = (await session.execute(select(Workflow).where(Workflow.id == "test_wf_1"))).scalar_one()
                wf2 = (await session.execute(select(Workflow).where(Workflow.id == "test_wf_2"))).scalar_one()
                assert wf1.status == "approved"
                assert wf2.status == "rejected"

        asyncio.run(verify_database_states())

        # 4. Trigger /reload to register approved tools dynamically
        response = client.post("/reload")
        assert response.status_code == 200
        reload_data = response.json()
        assert reload_data["status"] == "reloaded"

        # 5. Verify the tool is registered within FastMCP and available to clients
        async def verify_mcp_registration():
            tools = await mcp.list_tools()
            tool_names = [t.name for t in tools]
            
            # The approved workflow should be registered
            assert "test_workflow_one" in tool_names
            # The rejected workflow should NOT be registered
            assert "test_workflow_two" not in tool_names
            
            # Built-in diagnostic tools should be preserved
            assert "get_proxy_status" in tool_names
            assert "preview_workflow_steps" in tool_names

        asyncio.run(verify_mcp_registration())
