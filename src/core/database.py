"""
Dell MCP — SQLite Persistence and Governance Database Manager
==============================================================

Provides standard database schema initialization and query layers for:
  - OpenAPI endpoint indexing (Contract A)
  - Clustered workflows (Contract B) and approval status
  - Governance audit logs
  - Pipeline stages execution status
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# File path resolved relative to project root
DB_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "governance.db"


def get_db_connection() -> sqlite3.Connection:
    """Create a connection to the SQLite database with row factory enabled."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite tables for governance and audit trails if they don't exist."""
    with get_db_connection() as conn:
        # 1. Pipeline status tracking
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_status (
                stage TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
            """
        )

        # 2. Ingested OpenAPI endpoints
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS endpoints (
                operation_id TEXT PRIMARY KEY,
                method TEXT NOT NULL,
                url TEXT NOT NULL,
                required_params TEXT NOT NULL,  -- JSON serialized list of strings
                community_id TEXT
            )
            """
        )

        # 3. Discovered workflow clusters
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                workflow_name TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                cluster_size INTEGER NOT NULL,
                confidence REAL NOT NULL,
                generated_description TEXT NOT NULL,
                approved INTEGER NOT NULL DEFAULT 0,  -- 0=pending, 1=approved, 2=rejected
                rejection_reason TEXT,
                community_id TEXT
            )
            """
        )

        # 4. Audit trail events
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                workflow_name TEXT,
                description TEXT NOT NULL,
                actor TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )

        # Populate default statuses if empty
        for stage in ["ingestionStatus", "graphStatus", "clusteringStatus", "mcpRuntimeStatus"]:
            conn.execute(
                "INSERT OR IGNORE INTO pipeline_status (stage, status) VALUES (?, ?)",
                (stage, "idle"),
            )
        conn.commit()


def set_pipeline_status(stage: str, status: str) -> None:
    """Set status of a pipeline stage (ingestion, graph, clustering, mcp)."""
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_status (stage, status) VALUES (?, ?)",
            (stage, status),
        )
        conn.commit()


def get_pipeline_statuses() -> Dict[str, str]:
    """Retrieve all pipeline stages statuses."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT stage, status FROM pipeline_status")
        return {row["stage"]: row["status"] for row in cursor.fetchall()}


def log_audit_event(
    event_type: str,
    status: str,
    description: str,
    workflow_name: Optional[str] = None,
    actor: str = "system",
) -> None:
    """Create a new audit trail event in the database."""
    event_id = f"evt_{datetime.now(timezone.utc).timestamp()}_{hash(description) & 0xffff}"
    timestamp = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_events (id, event_type, status, workflow_name, description, actor, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, event_type, status, workflow_name, description, actor, timestamp),
        )
        conn.commit()


def save_endpoints(endpoints_list: List[Dict[str, Any]]) -> None:
    """Bulk save endpoints (Contract A) and clear old indices."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM endpoints")
        for ep in endpoints_list:
            conn.execute(
                """
                INSERT INTO endpoints (operation_id, method, url, required_params, community_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    ep["operation_id"],
                    ep["method"],
                    ep["url"],
                    json.dumps(ep.get("required_params", [])),
                    ep.get("community_id"),
                ),
            )
        conn.commit()


def get_all_endpoints() -> List[Dict[str, Any]]:
    """Retrieve all endpoints with parsed parameters."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM endpoints")
        results = []
        for row in cursor.fetchall():
            results.append(
                {
                    "operation_id": row["operation_id"],
                    "method": row["method"],
                    "url": row["url"],
                    "required_params": json.loads(row["required_params"]),
                    "community_id": row["community_id"],
                }
            )
        return results


def save_workflows(workflows_list: List[Dict[str, Any]]) -> None:
    """Bulk save discovered workflow clusters, preserving approved status if exists."""
    with get_db_connection() as conn:
        # Load existing approval status for preservation
        cursor = conn.execute("SELECT id, approved, rejection_reason, workflow_name, generated_description FROM workflows")
        existing = {row["id"]: dict(row) for row in cursor.fetchall()}

        conn.execute("DELETE FROM workflows")
        for wf in workflows_list:
            wf_id = wf["id"]
            approved = 0
            rejection_reason = None
            wf_name = wf["workflow_name"]
            wf_desc = wf["generated_description"]

            if wf_id in existing:
                approved = existing[wf_id]["approved"]
                rejection_reason = existing[wf_id]["rejection_reason"]
                # Keep edited values if the user had modified them
                if existing[wf_id]["workflow_name"] != wf_name:
                    wf_name = existing[wf_id]["workflow_name"]
                if existing[wf_id]["generated_description"] != wf_desc:
                    wf_desc = existing[wf_id]["generated_description"]

            conn.execute(
                """
                INSERT INTO workflows (id, workflow_name, risk_level, cluster_size, confidence, generated_description, approved, rejection_reason, community_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wf_id,
                    wf_name,
                    wf["risk_level"],
                    wf["cluster_size"],
                    wf["confidence"],
                    wf_desc,
                    approved,
                    rejection_reason,
                    wf.get("community_id", wf_id),
                ),
            )
        conn.commit()


def get_workflows(approved_only: bool = False, pending_only: bool = False) -> List[Dict[str, Any]]:
    """Retrieve workflows and associate underlying endpoints based on community_id."""
    with get_db_connection() as conn:
        query = "SELECT * FROM workflows"
        params = []
        if approved_only:
            query += " WHERE approved = 1"
        elif pending_only:
            query += " WHERE approved = 0"

        wf_cursor = conn.execute(query, params)
        workflows = [dict(row) for row in wf_cursor.fetchall()]

        # Map endpoints to their workflows by community_id
        ep_cursor = conn.execute("SELECT * FROM endpoints")
        endpoints = [dict(row) for row in ep_cursor.fetchall()]

        from collections import defaultdict
        community_to_endpoints = defaultdict(list)
        for ep in endpoints:
            if ep["community_id"]:
                community_to_endpoints[ep["community_id"]].append(
                    {
                        "operationId": ep["operation_id"],
                        "method": ep["method"],
                        "url": ep["url"],
                    }
                )

        results = []
        for wf in workflows:
            wf_id = wf["id"]
            comm_id = wf["community_id"] or wf_id
            underlying = community_to_endpoints[comm_id]

            # In case some nodes were direct mapping or Leiden generated empty groups, default to itself
            if not underlying:
                # Search for direct match
                underlying = [
                    ep for ep in endpoints if ep["operation_id"] == wf_id
                ]

            results.append(
                {
                    "id": wf_id,
                    "workflowName": wf["workflow_name"],
                    "riskLevel": wf["risk_level"],
                    "clusterSize": len(underlying) or wf["cluster_size"],
                    "confidence": wf["confidence"],
                    "generatedDescription": wf["generated_description"],
                    "approved": wf["approved"],
                    "rejectionReason": wf["rejection_reason"],
                    "communityId": comm_id,
                    "underlyingEndpoints": underlying,
                }
            )
        return results
