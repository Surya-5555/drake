from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.cli.exceptions import DellCLIError
from src.core.database import (
    async_session,
    get_db_connection,
    get_workflows,
    Workflow,
)
from .bridge import AsyncServiceBridge


class GovernanceCLIService:
    """Adapter for workflows approval states and audit records."""

    def _get_mapped_workflows(self, status: int) -> List[Dict[str, Any]]:
        try:
            wfs = get_workflows()
            return [w for w in wfs if w.get("approved") == status]
        except Exception as e:
            raise DellCLIError(
                title="Governance Queries Failed",
                cause=str(e),
                impact="Workflow lists cannot be accessed.",
                action="Verify SQLite integrity check.",
            )

    def get_pending(self) -> List[Dict[str, Any]]:
        return self._get_mapped_workflows(0)

    def get_approved(self) -> List[Dict[str, Any]]:
        return self._get_mapped_workflows(1)

    def get_rejected(self) -> List[Dict[str, Any]]:
        return self._get_mapped_workflows(2)

    def review_workflow(self, workflow_id: str) -> Dict[str, Any]:
        async def _async_review() -> Dict[str, Any]:
            async with async_session() as session:
                result = await session.execute(
                    select(Workflow)
                    .where(Workflow.id == workflow_id)
                    .options(selectinload(Workflow.steps))
                )
                wf = result.scalar_one_or_none()
                if not wf:
                    raise DellCLIError(
                        title="Workflow Not Found",
                        cause=f"ID '{workflow_id}' does not match any database record.",
                        impact="Detailed step audit cannot be displayed.",
                        action="Check target workflow ID using 'dell-mcp governance pending'.",
                    )
                steps_data = []
                for s in wf.steps:
                    steps_data.append(
                        {
                            "step_order": s.step_order,
                            "method": s.method,
                            "url": s.url,
                            "operation_id": s.operation_id,
                        }
                    )
                return {
                    "id": wf.id,
                    "displayName": wf.display_name,
                    "systemName": wf.system_name,
                    "riskLevel": wf.risk_level,
                    "clusterSize": wf.cluster_size,
                    "confidence": wf.confidence,
                    "generatedDescription": wf.generated_description,
                    "approved": wf.approved,
                    "rejectionReason": wf.rejection_reason,
                    "steps": steps_data,
                }

        return AsyncServiceBridge.run(_async_review())  # type: ignore[no-any-return]

    def approve_workflow(self, workflow_id: str) -> None:
        async def _async_approve() -> None:
            async with async_session() as session:
                result = await session.execute(
                    select(Workflow).where(Workflow.id == workflow_id)
                )
                wf = result.scalar_one_or_none()
                if not wf:
                    raise DellCLIError(
                        title="Workflow Approval Aborted",
                        cause=f"ID '{workflow_id}' not found.",
                        impact="Approved state cannot be applied.",
                        action="Check spelling of target workflow ID.",
                    )
                wf.approved = 1  # type: ignore[assignment]
                wf.rejection_reason = None  # type: ignore[assignment]
                wf.approved_by = "admin"  # type: ignore[assignment]
                wf.approved_at = datetime.now(timezone.utc).isoformat()  # type: ignore[assignment]

                # Write direct sync update to SQLite workflows table
                with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                    conn.execute(
                        "UPDATE workflows SET approved = 1, rejection_reason = NULL WHERE id = ?",
                        (workflow_id,),
                    )
                    conn.commit()
                await session.commit()

        AsyncServiceBridge.run(_async_approve())

    def reject_workflow(self, workflow_id: str, reason: str) -> None:
        async def _async_reject() -> None:
            async with async_session() as session:
                result = await session.execute(
                    select(Workflow).where(Workflow.id == workflow_id)
                )
                wf = result.scalar_one_or_none()
                if not wf:
                    raise DellCLIError(
                        title="Workflow Rejection Aborted",
                        cause=f"ID '{workflow_id}' not found.",
                        impact="Rejected state cannot be applied.",
                        action="Check spelling of target workflow ID.",
                    )
                wf.approved = 2  # type: ignore[assignment]
                wf.rejection_reason = reason  # type: ignore[assignment]

                with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                    conn.execute(
                        "UPDATE workflows SET approved = 2, rejection_reason = ? WHERE id = ?",
                        (reason, workflow_id),
                    )
                    conn.commit()
                await session.commit()

        AsyncServiceBridge.run(_async_reject())
