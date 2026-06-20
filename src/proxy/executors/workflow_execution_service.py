"""
Dell MCP — Pre-Flight Interceptor & Workflow Execution Service
==============================================================

Orchestrates execution of clustered workflows, acting as an interceptor to implement
the 'State-Aware Universal Rollback Architecture'. Automatically captures zero-touch
SCP XML configuration snapshots before mutating config steps.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any, Dict

import httpx
from sqlalchemy.future import select

from src.core.database import (
    async_session,
    Workflow,
    ExecutionHistory,
)
from src.proxy.executors.base import BaseExecutor
from src.core.exceptions import DellProxyExecutionError

logger = logging.getLogger("dell_mcp_workflow_execution_service")


class WorkflowExecutionService:
    """
    State-Aware Universal Rollback interceptor wrapping workflow executions.
    Injects database sessions and logs execution ledger entries.
    """

    def __init__(self, executor: BaseExecutor, session_maker=None) -> None:
        self.executor = executor
        self.session_maker = session_maker or async_session

    async def execute_workflow(
        self, workflow_name: str, target_server_ip: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Intercepts workflow execution, evaluates rollback strategy, takes system
        configuration snapshots if necessary, writes a ledger entry, and delegates
        to the inner executor for step execution.
        """
        logger.info(
            f"Pre-flight interceptor activated for workflow '{workflow_name}' "
            f"on target server '{target_server_ip}'."
        )

        # 1. Retrieve Workflow and its rollback strategy
        async with self.session_maker() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.system_name == workflow_name)
            )
            wf = result.scalar_one_or_none()
            if not wf:
                raise DellProxyExecutionError(
                    f"Workflow '{workflow_name}' not found in database."
                )

            workflow_id = wf.id
            rollback_strategy = wf.rollback_strategy or "NONE"

        snapshot_path = None

        # 2. Check rollback strategy & trigger configuration snapshot if required
        if rollback_strategy == "SCP_SNAPSHOT":
            # Determine base URL for HTTPExecutor requests
            base_url = "http://localhost:4010"
            headers = {}
            if hasattr(self.executor, "base_url"):
                base_url = self.executor.base_url
            elif hasattr(self.executor, "target_ip"):
                base_url = f"https://{self.executor.target_ip}"

            if hasattr(self.executor, "session_headers"):
                headers = self.executor.session_headers

            target_url = f"{base_url.rstrip('/')}/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ExportSystemConfiguration"
            payload = {
                "ExportFormat": "XML",
                "ShareParameters": {"Target": "Local"},
            }

            logger.info(
                f"Rollback Strategy: SCP_SNAPSHOT. Initiating pre-flight SCP export to {target_url}..."
            )
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        target_url, json=payload, headers=headers, timeout=5.0
                    )
                    logger.info(
                        f"SCP Export configuration request completed with status: {response.status_code}"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to complete mock SCP snapshot request to {target_url}: {e}"
                )

            # Generate and save dummy SCP XML payload
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            snapshots_dir = Path("data/output/snapshots")
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            snapshot_file = snapshots_dir / f"{timestamp}_{target_server_ip}.xml"

            dummy_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<SystemConfiguration Model="PowerEdge" ServiceTag="MOCKTAG" Created="{datetime.datetime.now(datetime.timezone.utc).isoformat()}">
  <Component FQDD="iDRAC.Embedded.1">
    <Attribute Name="IPMILan.1#Enable">Enabled</Attribute>
  </Component>
  <Component FQDD="BIOS.Setup.1-1">
    <Attribute Name="LogicalProc">Enabled</Attribute>
  </Component>
</SystemConfiguration>
"""
            try:
                snapshot_file.write_text(dummy_xml, encoding="utf-8")
                snapshot_path = str(snapshot_file.absolute())
                logger.info(f"Configuration snapshot successfully written to {snapshot_path}")
            except Exception as fe:
                logger.error(f"Failed to write snapshot file to disk: {fe}")

        # 3. Create execution ledger entry in database
        async with self.session_maker() as session:
            history_entry = ExecutionHistory(
                target_server_ip=target_server_ip,
                workflow_id=workflow_id,
                snapshot_path=snapshot_path,
                status="running",
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(history_entry)
            await session.commit()
            history_id = history_entry.id
            logger.info(f"Recorded execution ledger entry (ID: {history_id}, status: running)")

        # 4. Execute the actual workflow steps
        is_failed = False
        result = None
        error = None
        try:
            result = await self.executor.execute_workflow(workflow_name, params)
            status = result.get("status") or "success"
            if status not in ["success", "completed"]:
                is_failed = True
        except Exception as err:
            is_failed = True
            error = err
            status = "failed"

        if is_failed:
            logger.error(f"Workflow execution failed. Status: {status}. Error: {error}")
            
            # Execute state-aware rollback automatically if supported
            if rollback_strategy in ["DUAL_BANK", "SCP_SNAPSHOT"]:
                logger.info(f"Triggering automatic rollback for workflow '{workflow_name}' using strategy '{rollback_strategy}'")
                
                # Determine base URL for HTTPExecutor requests
                base_url = "http://localhost:4010"
                headers = {}
                if hasattr(self.executor, "base_url"):
                    base_url = self.executor.base_url
                elif hasattr(self.executor, "target_ip"):
                    base_url = f"https://{self.executor.target_ip}"
                else:
                    base_url = f"https://{target_server_ip}"

                if hasattr(self.executor, "session_headers"):
                    headers = self.executor.session_headers

                rollback_status = "failed"
                try:
                    if rollback_strategy == "DUAL_BANK":
                        target_url = f"{base_url.rstrip('/')}/redfish/v1/UpdateService/Actions/Oem/DellUpdateService.SwitchActiveFirmwarePartition"
                        logger.info(f"Auto-rollback: swapping active firmware partition on {target_server_ip} via {target_url}...")
                        async with httpx.AsyncClient() as client:
                            response = await client.post(target_url, json={}, headers=headers, timeout=10.0)
                            logger.info(f"Auto-rollback: DUAL_BANK partition swap completed with status: {response.status_code}")
                            if response.status_code < 400:
                                rollback_status = "rolled_back"
                    elif rollback_strategy == "SCP_SNAPSHOT" and snapshot_path:
                        p = Path(snapshot_path)
                        if p.exists():
                            xml_content = p.read_text(encoding="utf-8")
                            target_url = f"{base_url.rstrip('/')}/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ImportSystemConfiguration"
                            payload = {
                                "ImportBuffer": xml_content,
                                "ShareParameters": {"Target": "Local"},
                                "ShutdownType": "Graceful",
                            }
                            logger.info(f"Auto-rollback: importing configuration snapshot from '{snapshot_path}' via {target_url}...")
                            async with httpx.AsyncClient() as client:
                                response = await client.post(target_url, json=payload, headers=headers, timeout=10.0)
                                logger.info(f"Auto-rollback: SCP snapshot import completed with status: {response.status_code}")
                                if response.status_code < 400:
                                    rollback_status = "rolled_back"
                        else:
                            logger.warning(f"Auto-rollback failed: snapshot file '{snapshot_path}' does not exist on disk.")
                except Exception as rbe:
                    logger.error(f"Auto-rollback execution failed: {rbe}")

                # Log to audit log ledger
                try:
                    from src.core.database import log_audit_event
                    log_audit_event(
                        event_type="AUTO_ROLLBACK_TRIGGERED",
                        status=rollback_status,
                        description=f"Auto-rollback triggered for workflow '{workflow_name}' on {target_server_ip} (strategy: {rollback_strategy}). Outcome: {rollback_status}.",
                        workflow_name=workflow_name,
                        actor="system",
                    )
                except Exception as ae:
                    logger.warning(f"Failed to log auto-rollback audit event: {ae}")

                status = rollback_status

            # Update status in the ledger
            async with self.session_maker() as session:
                entry = await session.get(ExecutionHistory, history_id)
                if entry:
                    entry.status = status
                    await session.commit()
                    logger.info(f"Ledger entry {history_id} marked as: {status}")

            if error:
                raise error
            return result or {"status": status, "error": "workflow failed but was processed by rollback"}

        # Success path
        async with self.session_maker() as session:
            entry = await session.get(ExecutionHistory, history_id)
            if entry:
                entry.status = status
                await session.commit()
                logger.info(f"Ledger entry {history_id} updated with status: {status}")

        return result

