"""
Dell MCP — Governance REST API Server
=====================================

Provides OpenAPI endpoints for the Next.js human-in-the-loop governance console.
Integrates SQLite state queries, workflow modifications, approvals, reloads,
NetworkX relationship mapping, and metrics aggregations.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


from src.core.database import (
    get_all_endpoints,
    get_db_connection,
    get_pipeline_statuses,
    get_workflows,
    log_audit_event,
    set_pipeline_status,
)

logger = logging.getLogger("dell_mcp_api")

app = FastAPI(
    title="Dell Enterprise MCP Proxy Governance API",
    version="1.0.0",
    docs_url="/docs",
)

# Enable CORS for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import aiosqlite

from src.core.database import DB_FILE

logger = logging.getLogger("dell_mcp_api")

app = FastAPI(
    title="Dell Enterprise MCP Proxy Governance API",
    version="1.0.0",
    docs_url="/docs",
)

# Phase 5: API Security - Restrict CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Phase 5: API Security - API Key Auth
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key_header: str = Security(api_key_header)):
    expected_api_key = os.getenv("DELL_MCP_API_KEY", "default_dev_key")
    if api_key_header == expected_api_key:
        return api_key_header
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate API key"
        )


class UpdateWorkflowPayload(BaseModel):
    displayName: Optional[str] = None
    workflowName: Optional[str] = None
    generatedDescription: str


class RejectWorkflowPayload(BaseModel):
    reason: str


async def log_audit_event_async(
    event_type: str,
    status: str,
    description: str,
    workflow_name: Optional[str] = None,
    actor: str = "system",
):
    import uuid

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """
            INSERT INTO audit_events (id, event_type, status, workflow_name, description, actor, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                event_type,
                status,
                workflow_name,
                description,
                actor,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()


@app.get("/api/v1/overview")
async def get_overview() -> Dict[str, Any]:
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute("SELECT COUNT(*) as c FROM endpoints") as c:
                row = await c.fetchone()
                endpoint_count = row["c"] if row else 0

            async with db.execute(
                "SELECT approved, COUNT(*) as c FROM workflows GROUP BY approved"
            ) as c:
                wf_counts = await c.fetchall()

            pending_count = 0
            approved_count = 0
            for row in wf_counts:
                if row["approved"] == 0:
                    pending_count += row["c"]
                elif row["approved"] == 1:
                    approved_count += row["c"]

            workflow_count = (
                pending_count
                + approved_count
                + sum(r["c"] for r in wf_counts if r["approved"] not in (0, 1))
            )

            async with db.execute("SELECT stage, status FROM pipeline_status") as c:
                statuses = {row["stage"]: row["status"] for row in await c.fetchall()}

        return {
            "endpointCount": endpoint_count,
            "workflowCount": workflow_count,
            "pendingReviewCount": pending_count,
            "registeredWorkflowCount": approved_count,
            "ingestionStatus": statuses.get("ingestionStatus", "complete"),
            "graphStatus": statuses.get("graphStatus", "complete"),
            "clusteringStatus": statuses.get("clusteringStatus", "complete"),
            "mcpRuntimeStatus": statuses.get("mcpRuntimeStatus", "complete"),
        }
    except Exception as err:
        logger.error(f"Overview failed: {err}")
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/v1/workflows/pending")
async def get_pending_workflows() -> List[Dict[str, Any]]:
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM workflows WHERE approved = 0"
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": r["id"],
                        "systemName": r["system_name"],
                        "displayName": r["display_name"],
                        "workflowName": r["display_name"],
                        "riskLevel": r["risk_level"],
                        "clusterSize": r["cluster_size"],
                        "confidence": r["confidence"],
                        "generatedDescription": r["generated_description"],
                        "approved": r["approved"],
                        "rejectionReason": r["rejection_reason"],
                        "communityId": r["community_id"],
                    }
                    for r in rows
                ]
    except Exception as err:
        logger.error(f"Pending workflows failed: {err}")
        raise HTTPException(status_code=500, detail=str(err))


@app.post(
    "/api/v1/workflows/{workflow_id}/approve", dependencies=[Depends(get_api_key)]
)
async def approve_workflow(workflow_id: str) -> Dict[str, str]:
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        ) as c:
            wf = await c.fetchone()

        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")

        await db.execute(
            "UPDATE workflows SET approved = 1, rejection_reason = NULL WHERE id = ?",
            (workflow_id,),
        )
        await db.commit()

    await log_audit_event_async(
        "workflow_approved",
        "success",
        f"Approved workflow cluster '{wf['display_name']}'",
        wf["system_name"],
        "admin",
    )

    await sync_workflow_mappings_async()
    return {"status": "approved"}


@app.post("/api/v1/workflows/{workflow_id}/reject", dependencies=[Depends(get_api_key)])
async def reject_workflow(
    workflow_id: str, payload: RejectWorkflowPayload
) -> Dict[str, str]:
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        ) as c:
            wf = await c.fetchone()

        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")

        await db.execute(
            "UPDATE workflows SET approved = 2, rejection_reason = ? WHERE id = ?",
            (payload.reason, workflow_id),
        )
        await db.commit()

    await log_audit_event_async(
        "workflow_rejected",
        "success",
        f"Rejected workflow '{wf['display_name']}'. Reason: {payload.reason}",
        wf["system_name"],
        "admin",
    )

    await sync_workflow_mappings_async()
    return {"status": "rejected"}


@app.patch("/api/v1/workflows/{workflow_id}", dependencies=[Depends(get_api_key)])
async def update_workflow(
    workflow_id: str, payload: UpdateWorkflowPayload
) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        ) as c:
            wf = await c.fetchone()

        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")

        display_name = payload.displayName or payload.workflowName
        if not display_name:
            raise HTTPException(status_code=400, detail="Either displayName or workflowName must be provided")

        await db.execute(
            "UPDATE workflows SET display_name = ?, generated_description = ? WHERE id = ?",
            (display_name, payload.generatedDescription, workflow_id),
        )
        await db.commit()

        async with db.execute(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        ) as c:
            updated_wf = await c.fetchone()

        if not updated_wf:
            raise HTTPException(
                status_code=404, detail="Workflow not found after update"
            )

    await log_audit_event_async(
        "workflow_updated",
        "success",
        f"Updated name to '{display_name}' and description.",
        display_name,
        "admin",
    )

    await sync_workflow_mappings_async()

    return {
        "id": updated_wf["id"],
        "systemName": updated_wf["system_name"],
        "displayName": updated_wf["display_name"],
        "workflowName": updated_wf["display_name"],
        "riskLevel": updated_wf["risk_level"],
        "clusterSize": updated_wf["cluster_size"],
        "confidence": updated_wf["confidence"],
        "generatedDescription": updated_wf["generated_description"],
        "approved": updated_wf["approved"],
        "rejectionReason": updated_wf["rejection_reason"],
        "communityId": updated_wf["community_id"],
    }


@app.post("/api/v1/mcp/reload", dependencies=[Depends(get_api_key)])
async def reload_mcp() -> Dict[str, str]:
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "INSERT OR REPLACE INTO pipeline_status (stage, status) VALUES (?, ?)",
                ("mcpRuntimeStatus", "running"),
            )
            await db.commit()

        await sync_workflow_mappings_async()

        # Call reload state attached in server.py
        if hasattr(app.state, "mcp_reload"):
            await app.state.mcp_reload()
            logger.info("Successfully triggered server.py reload.")

        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "INSERT OR REPLACE INTO pipeline_status (stage, status) VALUES (?, ?)",
                ("mcpRuntimeStatus", "complete"),
            )
            await db.commit()

        await log_audit_event_async(
            "mcp_registered", "success", "FastMCP reload triggered.", actor="admin"
        )
        return {"status": "reloaded"}
    except Exception as err:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "INSERT OR REPLACE INTO pipeline_status (stage, status) VALUES (?, ?)",
                ("mcpRuntimeStatus", "error"),
            )
            await db.commit()

        await log_audit_event_async(
            "mcp_registered", "error", f"Reload failed: {err}", actor="admin"
        )
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/v1/graph")
async def get_graph() -> Dict[str, Any]:
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM endpoints") as c:
                eps = list(await c.fetchall())
            async with db.execute("SELECT * FROM edges") as c:
                edges = list(await c.fetchall())
            async with db.execute("SELECT * FROM workflows") as c:
                wfs = list(await c.fetchall())

        nodes_list = [
            {
                "id": ep["operation_id"],
                "method": ep["method"],
                "label": ep["url"],
                "communityId": ep["community_id"] or "unclustered",
            }
            for ep in eps
        ]

        edges_list = [
            {
                "id": f"edge_{idx}",
                "source": edge["source"],
                "target": edge["target"],
            }
            for idx, edge in enumerate(edges)
        ]

        communities_list = [
            {
                "id": wf["community_id"] or wf["id"],
                "systemName": wf["system_name"],
                "displayName": wf["display_name"],
                "workflowName": wf["display_name"],
                "size": wf["cluster_size"],
                "confidence": wf["confidence"],
            }
            for wf in wfs
        ]

        return {
            "nodes": nodes_list,
            "edges": edges_list,
            "communities": communities_list,
        }
    except Exception as err:
        logger.error(f"Graph query failed: {err}")
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/v1/metrics")
async def get_metrics() -> Dict[str, Any]:
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM endpoints") as c:
                eps = list(await c.fetchall())
            async with db.execute("SELECT * FROM workflows") as c:
                wfs = list(await c.fetchall())

        raw_endpoint_count = len(eps)
        workflow_count = len(wfs)

        if workflow_count == 0:
            reduction_ratio = 1.0
            clustering_coverage = 0.0
            token_savings = 0.0
        else:
            reduction_ratio = round(raw_endpoint_count / workflow_count, 1)
            clustered_endpoints = sum(1 for ep in eps if ep["community_id"] is not None)
            clustering_coverage = (
                round((clustered_endpoints / raw_endpoint_count) * 100, 1)
                if raw_endpoint_count > 0
                else 0.0
            )

            raw_tokens = raw_endpoint_count * 400
            clustered_tokens = workflow_count * 200
            token_savings = (
                round((1 - (clustered_tokens / raw_tokens)) * 100, 1)
                if raw_tokens > 0
                else 0.0
            )

        approved_count = sum(1 for w in wfs if w["approved"] == 1)
        rejected_count = sum(1 for w in wfs if w["approved"] == 2)
        pending_count = sum(1 for w in wfs if w["approved"] == 0)

        distribution = [
            {
                "systemName": wf["system_name"],
                "displayName": wf["display_name"],
                "workflowName": wf["display_name"],
                "endpointCount": wf["cluster_size"],
            }
            for wf in wfs
        ]

        return {
            "endpointReductionRatio": reduction_ratio,
            "workflowCount": workflow_count,
            "tokenSavingsPercent": token_savings,
            "clusteringCoveragePercent": clustering_coverage,
            "approvedCount": approved_count,
            "rejectedCount": rejected_count,
            "pendingCount": pending_count,
            "rawEndpointCount": raw_endpoint_count,
            "workflowDistribution": distribution,
        }
    except Exception as err:
        logger.error(f"Metrics query failed: {err}")
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/v1/audit/events")
async def get_audit_events() -> List[Dict[str, Any]]:
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM audit_events ORDER BY timestamp DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": r["id"],
                        "eventType": r["event_type"],
                        "status": r["status"],
                        "workflowName": r["workflow_name"],
                        "description": r["description"],
                        "actor": r["actor"],
                        "timestamp": r["timestamp"],
                    }
                    for r in rows
                ]
    except Exception as err:
        logger.error(f"Audit events query failed: {err}")
        raise HTTPException(status_code=500, detail=str(err))


async def sync_workflow_mappings_async() -> None:
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM workflows WHERE approved = 1") as c:
                approved_wfs = list(await c.fetchall())

            steps_mapping = {}
            for wf in approved_wfs:
                name = wf["system_name"]
                async with db.execute(
                    "SELECT * FROM endpoints WHERE community_id = ? ORDER BY operation_id",
                    (wf["community_id"],),
                ) as c:
                    eps = await c.fetchall()

                steps = [
                    {
                        "step_id": idx + 1,
                        "name": ep["operation_id"],
                        "method": ep["method"],
                        "url": ep["url"],
                        "params": {},
                    }
                    for idx, ep in enumerate(eps)
                ]

                steps_mapping[name] = {
                    "name": name,
                    "description": wf["generated_description"],
                    "steps": steps,
                }

        output_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data"
            / "output"
            / "workflow_mapping.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump({"workflows": steps_mapping}, f, indent=2)

        logger.info(
            f"Synchronized {len(approved_wfs)} approved workflows to {output_path}"
        )
    except Exception as err:
        logger.error(f"Syncing workflow mappings failed: {err}")
