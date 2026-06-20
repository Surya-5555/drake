import os
import pytest
import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai_clustering.schemas.workflow import Workflow as WorkflowSchema
from src.core.database import (
    async_session,
    init_db,
    Workflow,
    EndpointStep,
    ExecutionHistory,
)
from src.proxy.executors.workflow_execution_service import WorkflowExecutionService
from src.proxy.server import revert_previous_action, execute_workflow_route


@pytest.mark.anyio
async def test_workflow_schema_pydantic():
    """Verify that the Workflow Pydantic schema supports rollback fields."""
    wf_data = {
        "id": "wf_test_123",
        "system_name": "test_rollback_workflow",
        "display_name": "Test Rollback Workflow",
        "risk_level": "medium",
        "cluster_size": 2,
        "confidence": 0.85,
        "generated_description": "A workflow to test Pydantic validation.",
        "approved": 1,
        "supports_rollback": True,
        "rollback_strategy": "SCP_SNAPSHOT",
    }
    
    schema = WorkflowSchema(**wf_data)
    assert schema.supports_rollback is True
    assert schema.rollback_strategy == "SCP_SNAPSHOT"

    # Default values check
    wf_data_defaults = {
        "id": "wf_test_456",
        "system_name": "test_default_workflow",
        "display_name": "Test Default Workflow",
    }
    schema_defaults = WorkflowSchema(**wf_data_defaults)
    assert schema_defaults.supports_rollback is False
    assert schema_defaults.rollback_strategy == "NONE"


@pytest.mark.anyio
async def test_execution_history_persistence():
    """Verify that ExecutionHistory can be created and queried in the DB."""
    # Ensure tables are initialized
    await init_db()

    async with async_session() as session:
        # Create a mock workflow first to satisfy any foreign keys if checked,
        # or just add execution history.
        wf = Workflow(
            id="wf_db_test",
            system_name="test_wf_db",
            display_name="Test WF DB",
            risk_level="high",
            cluster_size=1,
            confidence=0.9,
            generated_description="test",
            supports_rollback=True,
            rollback_strategy="DUAL_BANK",
        )
        session.add(wf)
        await session.commit()

        history = ExecutionHistory(
            target_server_ip="192.168.1.50",
            workflow_id="wf_db_test",
            snapshot_path="/tmp/snapshot_test.xml",
            status="completed",
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(history)
        await session.commit()
        history_id = history.id

    # Retrieve and verify
    async with async_session() as session:
        retrieved = await session.get(ExecutionHistory, history_id)
        assert retrieved is not None
        assert retrieved.target_server_ip == "192.168.1.50"
        assert retrieved.workflow_id == "wf_db_test"
        assert retrieved.snapshot_path == "/tmp/snapshot_test.xml"
        assert retrieved.status == "completed"


@pytest.mark.anyio
@patch("src.proxy.executors.workflow_execution_service.httpx.AsyncClient")
async def test_interceptor_snapshot_and_ledger(mock_httpx_client):
    """Verify that WorkflowExecutionService intercepts calls, runs SCP snapshot, and writes the ledger."""
    await init_db()

    # Mock HTTP call response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

    # Mock inner executor
    mock_executor = MagicMock()
    mock_executor.execute_workflow = AsyncMock(return_value={"status": "success"})

    async with async_session() as session:
        # Insert a workflow configured with SCP_SNAPSHOT
        wf = Workflow(
            id="wf_scp_test",
            system_name="scp_workflow",
            display_name="SCP Workflow",
            risk_level="high",
            cluster_size=1,
            confidence=0.9,
            generated_description="test",
            supports_rollback=True,
            rollback_strategy="SCP_SNAPSHOT",
        )
        session.add(wf)
        await session.commit()

    service = WorkflowExecutionService(mock_executor)
    
    # Execute workflow via the service
    params = {"param1": "val1"}
    result = await service.execute_workflow("scp_workflow", "192.168.1.100", params)

    assert result["status"] == "success"
    mock_executor.execute_workflow.assert_called_once_with("scp_workflow", params)

    # Check if ledger entry was created
    async with async_session() as session:
        from sqlalchemy.future import select
        db_result = await session.execute(
            select(ExecutionHistory)
            .where(ExecutionHistory.target_server_ip == "192.168.1.100")
            .order_by(ExecutionHistory.timestamp.desc())
        )
        history = db_result.scalars().first()
        assert history is not None
        assert history.workflow_id == "wf_scp_test"
        assert history.status == "success"
        assert history.snapshot_path is not None
        assert "192.168.1.100.xml" in history.snapshot_path

        # Verify file exists on disk
        snapshot_file = Path(history.snapshot_path)
        assert snapshot_file.exists()
        assert "<SystemConfiguration" in snapshot_file.read_text()

        # Clean up snapshot file
        if snapshot_file.exists():
            snapshot_file.unlink()


@pytest.mark.anyio
@patch("httpx.AsyncClient")
async def test_revert_previous_action_dual_bank(mock_httpx_client):
    """Verify that revert_previous_action executes DUAL_BANK partition swap."""
    await init_db()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

    # Create dummy workflow and history entry
    async with async_session() as session:
        wf = Workflow(
            id="wf_dual_bank_test",
            system_name="firmware_update_wf",
            display_name="Firmware Update Workflow",
            risk_level="high",
            cluster_size=1,
            confidence=0.9,
            generated_description="test",
            supports_rollback=True,
            rollback_strategy="DUAL_BANK",
        )
        session.add(wf)
        await session.commit()

        history = ExecutionHistory(
            target_server_ip="192.168.1.200",
            workflow_id="wf_dual_bank_test",
            snapshot_path=None,
            status="success",
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(history)
        await session.commit()

    # Call revert
    message = await revert_previous_action("192.168.1.200")
    assert "Successfully reverted firmware" in message
    assert "Dual-Bank swap" in message

    # Verify the HTTP POST request to swap boot bank was made
    mock_client_instance.post.assert_called_once()
    args, kwargs = mock_client_instance.post.call_args
    assert "DellUpdateService.SwitchActiveFirmwarePartition" in args[0]


@pytest.mark.anyio
@patch("httpx.AsyncClient")
async def test_revert_previous_action_scp_snapshot(mock_httpx_client, tmp_path):
    """Verify that revert_previous_action restores SCP configurations from XML snapshot."""
    await init_db()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response
    mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

    # Create dummy XML snapshot file
    xml_file = tmp_path / "snapshot.xml"
    xml_file.write_text("<SystemConfiguration><Attribute Name='Test'>Enabled</Attribute></SystemConfiguration>")

    async with async_session() as session:
        wf = Workflow(
            id="wf_scp_revert_test",
            system_name="bios_config_wf",
            display_name="BIOS Configuration Workflow",
            risk_level="high",
            cluster_size=1,
            confidence=0.9,
            generated_description="test",
            supports_rollback=True,
            rollback_strategy="SCP_SNAPSHOT",
        )
        session.add(wf)
        await session.commit()

        history = ExecutionHistory(
            target_server_ip="192.168.1.250",
            workflow_id="wf_scp_revert_test",
            snapshot_path=str(xml_file),
            status="success",
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(history)
        await session.commit()

    # Call revert
    message = await revert_previous_action("192.168.1.250")
    assert "Successfully reverted configuration" in message
    assert "SCP snapshot" in message

    # Verify the HTTP POST request to import configuration was made with the XML payload
    mock_client_instance.post.assert_called_once()
    args, kwargs = mock_client_instance.post.call_args
    assert "ImportSystemConfiguration" in args[0]
    assert kwargs["json"]["ImportBuffer"] == xml_file.read_text()


@pytest.mark.anyio
async def test_revert_previous_action_none():
    """Verify that revert_previous_action refuses to revert irreversible changes."""
    await init_db()

    async with async_session() as session:
        wf = Workflow(
            id="wf_none_revert_test",
            system_name="factory_reset_wf",
            display_name="Factory Reset Workflow",
            risk_level="high",
            cluster_size=1,
            confidence=0.9,
            generated_description="test",
            supports_rollback=False,
            rollback_strategy="NONE",
        )
        session.add(wf)
        await session.commit()

        history = ExecutionHistory(
            target_server_ip="192.168.1.222",
            workflow_id="wf_none_revert_test",
            snapshot_path=None,
            status="success",
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(history)
        await session.commit()

    # Call revert
    message = await revert_previous_action("192.168.1.222")
    assert "Action cannot be reverted. Previous execution was flagged as an irreversible destructive action." in message
