from typing import Any, Dict, List

from src.cli.exceptions import DellCLIError
from src.core.database import get_db_connection


class AuditCLIService:
    """Adapter for security audit trails and log analyses."""

    def get_events(self) -> List[Dict[str, Any]]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                cursor = conn.execute(
                    "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT 50"
                )
                return [
                    {
                        "id": r["id"],
                        "event_type": r["event_type"],
                        "status": r["status"],
                        "workflow_name": r["workflow_name"],
                        "description": r["description"],
                        "actor": r["actor"],
                        "timestamp": r["timestamp"],
                    }
                    for r in cursor.fetchall()
                ]
        except Exception as e:
            raise DellCLIError(
                title="Audit Trail Log Failed",
                cause=str(e),
                impact="Security events cannot be extracted.",
                action="Verify audit_events table structure.",
            )

    def get_executions(self) -> List[Dict[str, Any]]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                cursor = conn.execute(
                    "SELECT * FROM execution_history ORDER BY timestamp DESC LIMIT 50"
                )
                return [
                    {
                        "id": r["id"],
                        "target_server_ip": r["target_server_ip"],
                        "workflow_id": r["workflow_id"],
                        "snapshot_path": r["snapshot_path"],
                        "status": r["status"],
                        "timestamp": r["timestamp"],
                    }
                    for r in cursor.fetchall()
                ]
        except Exception as e:
            raise DellCLIError(
                title="Execution Ledger Query Failed",
                cause=str(e),
                impact="Operational log history cannot be accessed.",
                action="Verify execution_history table structure.",
            )
