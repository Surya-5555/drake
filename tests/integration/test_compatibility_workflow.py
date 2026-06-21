import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from src.core.database import (
    init_db_sync,
    get_db_connection,
    save_workflows,
    async_session,
    DeviceInventory,
)
from src.core.exceptions import DellProxyExecutionError
from src.core.compatibility.orchestrator import (
    WorkflowExecutionManager,
    CompatibilityPolicyViolation,
)
from src.core.compatibility.models import (
    CompatibilityStatus,
    DeviceFacts,
    CompatibilityReport,
)


@pytest.fixture(autouse=True)
def setup_workflow_db():
    init_db_sync()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoints")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM audit_events")
        conn.execute("DELETE FROM device_inventory")
        conn.execute("DELETE FROM compatibility_reports")
        conn.commit()
    yield
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoints")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM audit_events")
        conn.execute("DELETE FROM device_inventory")
        conn.execute("DELETE FROM compatibility_reports")
        conn.commit()


@pytest.mark.asyncio
async def test_orchestrator_workflow_not_found():
    manager = WorkflowExecutionManager()
    with pytest.raises(
        DellProxyExecutionError, match="Workflow 'non_existent' not found"
    ):
        await manager.execute_workflow_with_validation("non_existent", {})


@pytest.mark.asyncio
async def test_orchestrator_invalid_policy_fallback(monkeypatch):
    # Seed workflow
    save_workflows(
        [
            {
                "id": "wf_policy_test",
                "workflow_name": "policy_test_wf",
                "risk_level": "low",
                "cluster_size": 1,
                "confidence": 0.9,
                "generated_description": "desc",
                "community_id": "c1",
            }
        ]
    )

    # Mock the rest of the flow
    mock_facts = DeviceFacts(
        target_ip="1.1.1.1", device_model="R750", bios_version="1.0.0"
    )
    monkeypatch.setattr(
        "src.core.compatibility.sources.CachedFactsProvider.get_device_facts",
        AsyncMock(return_value=mock_facts),
    )

    mock_report = CompatibilityReport(
        id="rep1",
        workflow_id="wf_policy_test",
        target_ip="1.1.1.1",
        status=CompatibilityStatus.BLOCK,
        compatibility_score=10,
        risk_score=90,
        blast_radius="NODE",
        confidence_score=100,
    )
    monkeypatch.setattr(
        "src.core.compatibility.engine.CompatibilityEngine.validate_workflow",
        AsyncMock(return_value=mock_report),
    )
    monkeypatch.setattr(
        "src.core.compatibility.repository.CompatibilityRepository.save_report",
        AsyncMock(),
    )

    manager = WorkflowExecutionManager()

    # Run with invalid policy -> should fallback to STRICT and raise policy violation
    with pytest.raises(
        CompatibilityPolicyViolation, match="STRICT Policy blocked execution"
    ):
        await manager.execute_workflow_with_validation(
            "policy_test_wf", {"target_ip": "1.1.1.1"}, policy="INVALID_POLICY_NAME"
        )


@pytest.mark.asyncio
async def test_orchestrator_naive_cache_timestamp(monkeypatch):
    save_workflows(
        [
            {
                "id": "wf_naive_cache",
                "workflow_name": "naive_cache_wf",
                "risk_level": "low",
                "cluster_size": 1,
                "confidence": 0.9,
                "generated_description": "desc",
                "community_id": "c1",
            }
        ]
    )

    # Seed fresh cache row with naive scan timestamp (no tzinfo)
    async with async_session() as session:
        naive_now = datetime.now()  # naive timestamp
        dev_row = DeviceInventory(
            id="dev_1",
            target_ip="1.1.1.2",
            device_model="PowerEdge R750",
            bios_version="2.12.0",
            lifecycle_controller_version="5.10.00.00",
            firmware_inventory="{}",
            last_scanned=naive_now.isoformat(),
        )
        session.add(dev_row)
        await session.commit()

    # Stub executors to prevent real executor calls
    mock_executor_res = {"status": "mock_executed"}
    monkeypatch.setattr(
        "src.proxy.executors.workflow_execution_service.WorkflowExecutionService.execute_workflow",
        AsyncMock(return_value=mock_executor_res),
    )

    # Mock engine return
    mock_report = CompatibilityReport(
        id="rep2",
        workflow_id="wf_naive_cache",
        target_ip="1.1.1.2",
        status=CompatibilityStatus.ALLOW,
        compatibility_score=100,
        risk_score=10,
        blast_radius="NODE",
        confidence_score=80,
    )
    monkeypatch.setattr(
        "src.core.compatibility.engine.CompatibilityEngine.validate_workflow",
        AsyncMock(return_value=mock_report),
    )

    manager = WorkflowExecutionManager()
    res = await manager.execute_workflow_with_validation(
        "naive_cache_wf", {"target_ip": "1.1.1.2"}, policy="WARN_ONLY"
    )
    assert res["status"] == "mock_executed"
    assert res["compatibility_assessment"]["report_id"] == "rep2"


@pytest.mark.asyncio
async def test_orchestrator_cache_failure_fallback_static(monkeypatch):
    save_workflows(
        [
            {
                "id": "wf_fallback",
                "workflow_name": "fallback_wf",
                "risk_level": "low",
                "cluster_size": 1,
                "confidence": 0.9,
                "generated_description": "desc",
                "community_id": "c1",
            }
        ]
    )

    # Trigger Redfish failure AND Cached lookup failure
    async def raise_error(*args, **kwargs):
        raise ValueError("Simulated network/DB error")

    monkeypatch.setattr(
        "src.core.compatibility.sources.RedfishFactsProvider.get_device_facts",
        raise_error,
    )
    monkeypatch.setattr(
        "src.core.compatibility.sources.CachedFactsProvider.get_device_facts",
        raise_error,
    )

    # Stub executors
    mock_executor_res = {"status": "mock_executed"}
    monkeypatch.setattr(
        "src.proxy.executors.workflow_execution_service.WorkflowExecutionService.execute_workflow",
        AsyncMock(return_value=mock_executor_res),
    )

    # We want to verify it falls back to StaticFactsProvider, which succeeds and calls engine
    engine_spy = AsyncMock(
        return_value=CompatibilityReport(
            id="rep3",
            workflow_id="wf_fallback",
            target_ip="1.1.1.3",
            status=CompatibilityStatus.ALLOW,
            compatibility_score=100,
            risk_score=10,
            blast_radius="NODE",
            confidence_score=80,
        )
    )
    monkeypatch.setattr(
        "src.core.compatibility.engine.CompatibilityEngine.validate_workflow",
        engine_spy,
    )

    manager = WorkflowExecutionManager()
    await manager.execute_workflow_with_validation(
        "fallback_wf", {"target_ip": "1.1.1.3"}, policy="WARN_ONLY"
    )

    # Verify the fallback facts were R750 (the static default)
    assert engine_spy.call_count == 1
    passed_facts = engine_spy.call_args[0][2]
    assert passed_facts.device_model == "PowerEdge R750"


@pytest.mark.asyncio
async def test_orchestrator_auto_live_refresh_low_confidence(monkeypatch):
    save_workflows(
        [
            {
                "id": "wf_refresh",
                "workflow_name": "refresh_wf",
                "risk_level": "low",
                "cluster_size": 1,
                "confidence": 0.9,
                "generated_description": "desc",
                "community_id": "c1",
            }
        ]
    )

    # Seed fresh cache but we will mock engine to return confidence score < 50
    async with async_session() as session:
        dev_row = DeviceInventory(
            id="dev_2",
            target_ip="1.1.1.4",
            device_model="PowerEdge R750",
            bios_version="2.12.0",
            lifecycle_controller_version="5.10.00.00",
            firmware_inventory="{}",
            last_scanned=datetime.now(timezone.utc).isoformat(),
        )
        session.add(dev_row)
        await session.commit()

    # Mocks
    mock_low_conf = CompatibilityReport(
        id="rep_low",
        workflow_id="wf_refresh",
        target_ip="1.1.1.4",
        status=CompatibilityStatus.ALLOW,
        compatibility_score=100,
        risk_score=10,
        blast_radius="NODE",
        confidence_score=40,
    )
    mock_high_conf = CompatibilityReport(
        id="rep_high",
        workflow_id="wf_refresh",
        target_ip="1.1.1.4",
        status=CompatibilityStatus.ALLOW,
        compatibility_score=100,
        risk_score=10,
        blast_radius="NODE",
        confidence_score=80,
    )

    validate_mock = AsyncMock(side_effect=[mock_low_conf, mock_high_conf])
    monkeypatch.setattr(
        "src.core.compatibility.engine.CompatibilityEngine.validate_workflow",
        validate_mock,
    )

    # Redfish facts mock
    mock_live_facts = DeviceFacts(
        target_ip="1.1.1.4",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        is_live=True,
    )
    redfish_mock = AsyncMock(return_value=mock_live_facts)
    monkeypatch.setattr(
        "src.core.compatibility.sources.RedfishFactsProvider.get_device_facts",
        redfish_mock,
    )
    monkeypatch.setattr(
        "src.core.compatibility.repository.CompatibilityRepository.save_device_facts",
        AsyncMock(),
    )

    # Stub executors
    mock_executor_res = {"status": "mock_executed"}
    monkeypatch.setattr(
        "src.proxy.executors.workflow_execution_service.WorkflowExecutionService.execute_workflow",
        AsyncMock(return_value=mock_executor_res),
    )

    manager = WorkflowExecutionManager()
    await manager.execute_workflow_with_validation(
        "refresh_wf", {"target_ip": "1.1.1.4"}, policy="WARN_ONLY"
    )

    # Verify auto live refresh was triggered (redfish called)
    assert redfish_mock.called
    assert validate_mock.call_count == 2


@pytest.mark.asyncio
async def test_orchestrator_low_confidence_policy_block(monkeypatch):
    save_workflows(
        [
            {
                "id": "wf_block_conf",
                "workflow_name": "block_conf_wf",
                "risk_level": "low",
                "cluster_size": 1,
                "confidence": 0.9,
                "generated_description": "desc",
                "community_id": "c1",
            }
        ]
    )

    # Mock engine to return confidence < 50
    mock_report = CompatibilityReport(
        id="rep_low",
        workflow_id="wf_block_conf",
        target_ip="1.1.1.5",
        status=CompatibilityStatus.ALLOW,
        compatibility_score=100,
        risk_score=10,
        blast_radius="NODE",
        confidence_score=30,
    )
    monkeypatch.setattr(
        "src.core.compatibility.engine.CompatibilityEngine.validate_workflow",
        AsyncMock(return_value=mock_report),
    )
    monkeypatch.setattr(
        "src.core.compatibility.sources.CachedFactsProvider.get_device_facts",
        AsyncMock(
            return_value=DeviceFacts(
                target_ip="1.1.1.5", device_model="R750", bios_version="1.0.0"
            )
        ),
    )

    # Auto refresh raises error so it cannot recover confidence score
    async def raise_error(*args, **kwargs):
        raise ValueError("Network down")

    monkeypatch.setattr(
        "src.core.compatibility.sources.RedfishFactsProvider.get_device_facts",
        raise_error,
    )

    manager = WorkflowExecutionManager()
    with pytest.raises(
        CompatibilityPolicyViolation,
        match="confidence score .* is below policy threshold",
    ):
        await manager.execute_workflow_with_validation(
            "block_conf_wf", {"target_ip": "1.1.1.5"}, policy="STRICT"
        )


@pytest.mark.asyncio
async def test_orchestrator_executor_backends(monkeypatch):
    save_workflows(
        [
            {
                "id": "wf_executors",
                "workflow_name": "executors_wf",
                "risk_level": "low",
                "cluster_size": 1,
                "confidence": 0.9,
                "generated_description": "desc",
                "community_id": "c1",
            }
        ]
    )

    # Stub validation and database
    mock_report = CompatibilityReport(
        id="rep_exec",
        workflow_id="wf_executors",
        target_ip="1.1.1.6",
        status=CompatibilityStatus.ALLOW,
        compatibility_score=100,
        risk_score=10,
        blast_radius="NODE",
        confidence_score=100,
    )
    monkeypatch.setattr(
        "src.core.compatibility.engine.CompatibilityEngine.validate_workflow",
        AsyncMock(return_value=mock_report),
    )
    monkeypatch.setattr(
        "src.core.compatibility.sources.CachedFactsProvider.get_device_facts",
        AsyncMock(
            return_value=DeviceFacts(
                target_ip="1.1.1.6", device_model="R750", bios_version="1.0.0"
            )
        ),
    )

    # Spy on WorkflowExecutionService initialization
    exec_spy = MagicMock()

    def mock_init(self, exec_inst):
        exec_spy(exec_inst)

    monkeypatch.setattr(
        "src.proxy.executors.workflow_execution_service.WorkflowExecutionService.__init__",
        mock_init,
    )
    monkeypatch.setattr(
        "src.proxy.executors.workflow_execution_service.WorkflowExecutionService.execute_workflow",
        AsyncMock(return_value={}),
    )

    manager = WorkflowExecutionManager()

    # 1. Test OMSDK Executor type selection
    monkeypatch.setenv("DELL_EXECUTOR_TYPE", "omsdk")
    await manager.execute_workflow_with_validation(
        "executors_wf", {"target_ip": "1.1.1.6"}, policy="STRICT"
    )
    from src.proxy.executors.dell_omsdk_executor import DellOMSDKExecutor

    assert isinstance(exec_spy.call_args[0][0], DellOMSDKExecutor)

    # 2. Test Mock Executor type selection
    exec_spy.reset_mock()
    mock_report.id = "rep_exec2"
    monkeypatch.setenv("DELL_EXECUTOR_TYPE", "mock")
    await manager.execute_workflow_with_validation(
        "executors_wf", {"target_ip": "1.1.1.6"}, policy="STRICT"
    )
    from src.proxy.executors.httpx_executor import MockExecutor

    assert isinstance(exec_spy.call_args[0][0], MockExecutor)


@pytest.mark.asyncio
async def test_orchestrator_cache_miss_live_redfish_success(monkeypatch):
    save_workflows(
        [
            {
                "id": "wf_live_success",
                "workflow_name": "live_success_wf",
                "risk_level": "low",
                "cluster_size": 1,
                "confidence": 0.9,
                "generated_description": "desc",
                "community_id": "c1",
            }
        ]
    )

    # Cache miss
    async def cache_raise(*args, **kwargs):
        raise ValueError("Cache miss")

    monkeypatch.setattr(
        "src.core.compatibility.sources.CachedFactsProvider.get_device_facts",
        cache_raise,
    )

    # Redfish success
    mock_facts = DeviceFacts(
        target_ip="1.1.1.7", device_model="PowerEdge R750", bios_version="2.12.0"
    )
    redfish_mock = AsyncMock(return_value=mock_facts)
    monkeypatch.setattr(
        "src.core.compatibility.sources.RedfishFactsProvider.get_device_facts",
        redfish_mock,
    )

    save_device_facts_spy = AsyncMock()
    monkeypatch.setattr(
        "src.core.compatibility.repository.CompatibilityRepository.save_device_facts",
        save_device_facts_spy,
    )

    # Stub validation and execution
    mock_report = CompatibilityReport(
        id="rep_live",
        workflow_id="wf_live_success",
        target_ip="1.1.1.7",
        status=CompatibilityStatus.ALLOW,
        compatibility_score=100,
        risk_score=10,
        blast_radius="NODE",
        confidence_score=100,
    )
    monkeypatch.setattr(
        "src.core.compatibility.engine.CompatibilityEngine.validate_workflow",
        AsyncMock(return_value=mock_report),
    )
    monkeypatch.setattr(
        "src.proxy.executors.workflow_execution_service.WorkflowExecutionService.execute_workflow",
        AsyncMock(return_value={}),
    )

    manager = WorkflowExecutionManager()
    await manager.execute_workflow_with_validation(
        "live_success_wf", {"target_ip": "1.1.1.7"}, policy="STRICT"
    )

    assert redfish_mock.called
    assert save_device_facts_spy.called


@pytest.mark.asyncio
async def test_orchestrator_auto_live_refresh_failure(monkeypatch):
    save_workflows(
        [
            {
                "id": "wf_refresh_fail",
                "workflow_name": "refresh_fail_wf",
                "risk_level": "low",
                "cluster_size": 1,
                "confidence": 0.9,
                "generated_description": "desc",
                "community_id": "c1",
            }
        ]
    )

    # Fresh cache facts (so use_live becomes False)
    mock_facts = DeviceFacts(
        target_ip="1.1.1.8",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        is_live=False,
        last_scanned=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        "src.core.compatibility.sources.CachedFactsProvider.get_device_facts",
        AsyncMock(return_value=mock_facts),
    )

    # Mock engine to return low confidence score < 50
    mock_report = CompatibilityReport(
        id="rep_refresh_fail",
        workflow_id="wf_refresh_fail",
        target_ip="1.1.1.8",
        status=CompatibilityStatus.ALLOW,
        compatibility_score=100,
        risk_score=10,
        blast_radius="NODE",
        confidence_score=30,
    )
    monkeypatch.setattr(
        "src.core.compatibility.engine.CompatibilityEngine.validate_workflow",
        AsyncMock(return_value=mock_report),
    )

    # Redfish query fails during auto refresh
    async def redfish_raise(*args, **kwargs):
        raise ValueError("Network down during refresh")

    monkeypatch.setattr(
        "src.core.compatibility.sources.RedfishFactsProvider.get_device_facts",
        redfish_raise,
    )

    # Stub execution
    monkeypatch.setattr(
        "src.proxy.executors.workflow_execution_service.WorkflowExecutionService.execute_workflow",
        AsyncMock(return_value={}),
    )

    manager = WorkflowExecutionManager()
    with pytest.raises(
        CompatibilityPolicyViolation,
        match="confidence score .* is below policy threshold",
    ):
        await manager.execute_workflow_with_validation(
            "refresh_fail_wf", {"target_ip": "1.1.1.8"}, policy="WARN_ONLY"
        )


@pytest.mark.asyncio
async def test_orchestrator_warn_only_policy_gates(monkeypatch):
    save_workflows(
        [
            {
                "id": "wf_warn_gate",
                "workflow_name": "warn_gate_wf",
                "risk_level": "low",
                "cluster_size": 1,
                "confidence": 0.9,
                "generated_description": "desc",
                "community_id": "c1",
            }
        ]
    )

    monkeypatch.setattr(
        "src.core.compatibility.sources.CachedFactsProvider.get_device_facts",
        AsyncMock(
            return_value=DeviceFacts(
                target_ip="1.1.1.9", device_model="R750", bios_version="1.0.0"
            )
        ),
    )

    # Stub engine validation to return WARN status
    mock_report = CompatibilityReport(
        id="rep_warn",
        workflow_id="wf_warn_gate",
        target_ip="1.1.1.9",
        status=CompatibilityStatus.WARN,
        compatibility_score=75,
        risk_score=40,
        blast_radius="NODE",
        confidence_score=80,
    )
    monkeypatch.setattr(
        "src.core.compatibility.engine.CompatibilityEngine.validate_workflow",
        AsyncMock(return_value=mock_report),
    )
    monkeypatch.setattr(
        "src.proxy.executors.workflow_execution_service.WorkflowExecutionService.execute_workflow",
        AsyncMock(return_value={"status": "executed"}),
    )

    manager = WorkflowExecutionManager()
    res = await manager.execute_workflow_with_validation(
        "warn_gate_wf", {"target_ip": "1.1.1.9"}, policy="WARN_ONLY"
    )
    assert res["compatibility_assessment"]["status"] == "WARN"
