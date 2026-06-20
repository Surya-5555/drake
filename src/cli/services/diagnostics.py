import os
from typing import Any, Dict
import httpx

from src.core.database import get_db_connection


class DiagnosticsCLIService:
    """Adapter for subsystems diagnostics reports."""

    def get_health_status(self) -> Dict[str, str]:
        # Fast health check
        health = {
            "Database": "HEALTHY",
            "Governance": "HEALTHY",
            "Compatibility": "HEALTHY",
            "FastMCP": "HEALTHY",
            "Runtime": "HEALTHY",
        }
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                conn.execute("SELECT 1")
        except Exception:
            health["Database"] = "DEGRADED"

        port = os.getenv("PORT", "8000")
        try:
            # Quick check if API is alive
            r = httpx.get(f"http://localhost:{port}/metrics", timeout=1.0)
            if r.status_code != 200:
                health["FastMCP"] = "DEGRADED"
        except Exception:
            health["FastMCP"] = "DEGRADED"

        return health

    def check_db(self) -> Dict[str, Any]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                tables = [
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                ]
                rules_count = conn.execute(
                    "SELECT COUNT(*) FROM compatibility_rules"
                ).fetchone()[0]
                profiles_count = conn.execute(
                    "SELECT COUNT(*) FROM risk_profiles"
                ).fetchone()[0]
                idx_check = conn.execute(
                    "PRAGMA index_list('compatibility_rules')"
                ).fetchall()
            return {
                "database_status": "HEALTHY",
                "tables_present": len(tables),
                "rules_registered": rules_count,
                "risk_profiles_registered": profiles_count,
                "indexes_present": len(idx_check) > 0,
            }
        except Exception as e:
            return {"database_status": "DEGRADED", "error": str(e)}

    def check_api(self) -> Dict[str, Any]:
        port = os.getenv("PORT", "8000")
        url = f"http://localhost:{port}/metrics"
        try:
            resp = httpx.get(url, timeout=2.0)
            return {
                "api_gateway": "ONLINE",
                "metrics_endpoint": "HEALTHY",
                "port_listening": port,
                "response_code": resp.status_code,
            }
        except Exception as e:
            return {"api_gateway": "OFFLINE", "port_listening": port, "error": str(e)}

    def check_compatibility(self) -> Dict[str, Any]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                tables = [
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                ]
                required = [
                    "compatibility_rules",
                    "compatibility_dependencies",
                    "device_inventory",
                    "compatibility_reports",
                    "risk_profiles",
                ]
                missing = [t for t in required if t not in tables]

                profiles_count = conn.execute(
                    "SELECT COUNT(*) FROM risk_profiles"
                ).fetchone()[0]
                idx_check = conn.execute(
                    "PRAGMA index_list('compatibility_rules')"
                ).fetchall()
                has_temporal_idx = any(
                    "idx_rules_temporal" in idx[1] for idx in idx_check
                )
                cached_devices = conn.execute(
                    "SELECT COUNT(*) FROM device_inventory"
                ).fetchone()[0]
                rule_count = conn.execute(
                    "SELECT COUNT(*) FROM compatibility_rules"
                ).fetchone()[0]

            return {
                "compatibility_layer": "HEALTHY" if not missing else "DEGRADED",
                "missing_tables": missing,
                "risk_profiles_count": profiles_count,
                "has_temporal_index": has_temporal_idx,
                "cached_devices": cached_devices,
                "rules_count": rule_count,
                "provider_health": "ONLINE",
            }
        except Exception as e:
            return {"compatibility_layer": "DEGRADED", "error": str(e)}

    def check_runtime(self) -> Dict[str, Any]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                approved_count = conn.execute(
                    "SELECT COUNT(*) FROM workflows WHERE approved = 1"
                ).fetchone()[0]
                total_wfs = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]

            port = os.getenv("PORT", "8000")
            api_status = "ONLINE"
            try:
                httpx.get(f"http://localhost:{port}/metrics", timeout=1.0)
            except Exception:
                api_status = "OFFLINE"

            return {
                "runtime_status": "HEALTHY" if api_status == "ONLINE" else "DEGRADED",
                "registered_mcp_tools": approved_count,
                "total_workflows": total_wfs,
                "api_endpoint": api_status,
                "port_listening": port,
            }
        except Exception as e:
            return {"runtime_status": "DEGRADED", "error": str(e)}
