from typing import Any, Dict

from src.cli.exceptions import DellCLIError
from src.core.database import get_db_connection
from .diagnostics import DiagnosticsCLIService


class SystemCLIService:
    """Adapter for global executive dashboard stats."""

    def get_overview_metrics(self) -> Dict[str, Any]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                eps_count = conn.execute("SELECT COUNT(*) FROM endpoints").fetchone()[0]
                wfs_count = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
                approved_count = conn.execute(
                    "SELECT COUNT(*) FROM workflows WHERE approved = 1"
                ).fetchone()[0]
                pending_count = conn.execute(
                    "SELECT COUNT(*) FROM workflows WHERE approved = 0"
                ).fetchone()[0]
                rejected_count = conn.execute(
                    "SELECT COUNT(*) FROM workflows WHERE approved = 2"
                ).fetchone()[0]
                rules_count = conn.execute(
                    "SELECT COUNT(*) FROM compatibility_rules"
                ).fetchone()[0]
                devices_count = conn.execute(
                    "SELECT COUNT(*) FROM device_inventory"
                ).fetchone()[0]
                exec_count = conn.execute(
                    "SELECT COUNT(*) FROM execution_history"
                ).fetchone()[0]
                violations_count = conn.execute(
                    "SELECT COUNT(*) FROM compatibility_reports WHERE status = 'BLOCK'"
                ).fetchone()[0]

            # Check online status
            health = DiagnosticsCLIService().get_health_status()

            return {
                "endpointCount": eps_count,
                "workflowCount": wfs_count,
                "approvedCount": approved_count,
                "pendingCount": pending_count,
                "rejectedCount": rejected_count,
                "compatibilityRulesCount": rules_count,
                "cachedDevicesCount": devices_count,
                "executionCount": exec_count,
                "violationsCount": violations_count,
                "health": health,
            }
        except Exception as e:
            raise DellCLIError(
                title="System Overview Collection Failed",
                cause=str(e),
                impact="Executive control stats cannot be retrieved.",
                action="Verify SQLite read permissions.",
            )
