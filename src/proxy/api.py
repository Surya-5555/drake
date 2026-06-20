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


import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
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
    import hashlib

    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT hash FROM audit_events ORDER BY rowid DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            previous_hash = row["hash"] if row and row["hash"] else "GENESIS_HASH"
            
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_str = f"{event_id}{event_type}{status}{workflow_name}{description}{actor}{timestamp}None{previous_hash}"
        new_hash = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()

        await db.execute(
            """
            INSERT INTO audit_events (id, event_type, status, workflow_name, description, actor, timestamp, metadata, previous_hash, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                status,
                workflow_name,
                description,
                actor,
                timestamp,
                None,
                previous_hash,
                new_hash,
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
            
            async with db.execute("SELECT * FROM endpoints") as cursor:
                endpoints_rows = await cursor.fetchall()

            from collections import defaultdict
            community_to_endpoints = defaultdict(list)
            for ep in endpoints_rows:
                if ep["community_id"]:
                    community_to_endpoints[ep["community_id"]].append(
                        {
                            "operationId": ep["operation_id"],
                            "method": ep["method"],
                            "url": ep["url"],
                            "path": ep["url"],
                        }
                    )

            results = []
            for r in rows:
                wf_id = r["id"]
                comm_id = r["community_id"] or wf_id
                underlying = community_to_endpoints[comm_id]
                if not underlying:
                    underlying = [
                        {
                            "operationId": ep["operation_id"],
                            "method": ep["method"],
                            "url": ep["url"],
                            "path": ep["url"],
                        }
                        for ep in endpoints_rows
                        if ep["operation_id"] == wf_id
                    ]
                results.append(
                    {
                        "id": wf_id,
                        "systemName": r["system_name"],
                        "displayName": r["display_name"],
                        "workflowName": r["display_name"],
                        "riskLevel": r["risk_level"],
                        "clusterSize": len(underlying) or r["cluster_size"],
                        "confidence": r["confidence"],
                        "generatedDescription": r["generated_description"],
                        "approved": r["approved"],
                        "rejectionReason": r["rejection_reason"],
                        "communityId": comm_id,
                        "underlyingEndpoints": underlying,
                    }
                )
            return results
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
            "UPDATE workflows SET approved = 1, rejection_reason = NULL, approved_by = ?, approved_at = ? WHERE id = ?",
            ("admin", datetime.now(timezone.utc).isoformat(), workflow_id),
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

        comm_id = updated_wf["community_id"] or workflow_id
        async with db.execute(
            "SELECT * FROM endpoints WHERE community_id = ? ORDER BY operation_id",
            (comm_id,),
        ) as c:
            eps = await c.fetchall()

        underlying = [
            {
                "operationId": ep["operation_id"],
                "method": ep["method"],
                "url": ep["url"],
                "path": ep["url"],
            }
            for ep in eps
        ]

        if not underlying:
            async with db.execute(
                "SELECT * FROM endpoints WHERE operation_id = ?",
                (workflow_id,),
            ) as c:
                eps = await c.fetchall()
            underlying = [
                {
                    "operationId": ep["operation_id"],
                    "method": ep["method"],
                    "url": ep["url"],
                    "path": ep["url"],
                }
                for ep in eps
            ]

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
        "clusterSize": len(underlying) or updated_wf["cluster_size"],
        "confidence": updated_wf["confidence"],
        "generatedDescription": updated_wf["generated_description"],
        "approved": updated_wf["approved"],
        "rejectionReason": updated_wf["rejection_reason"],
        "communityId": updated_wf["community_id"],
        "underlyingEndpoints": underlying,
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

            # Calculate actual tokens using length heuristic (len // 4)
            raw_tokens = sum(len(str(ep["request_schema"] or "")) // 4 + len(str(ep["response_schema"] or "")) // 4 for ep in eps)
            clustered_tokens = sum(len(str(wf["generated_description"] or "")) // 4 for wf in wfs)
            
            # Avoid divide by zero
            raw_tokens = max(raw_tokens, 1)
            token_savings = (
                round((1 - (clustered_tokens / raw_tokens)) * 100, 1)
                if raw_tokens > clustered_tokens
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


@app.get("/metrics")
async def prometheus_metrics():
    from fastapi.responses import PlainTextResponse
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT COUNT(*) as c FROM endpoints") as c:
                row = await c.fetchone()
                endpoint_count = row["c"] if row else 0

            async with db.execute("SELECT approved, COUNT(*) as c FROM workflows GROUP BY approved") as c:
                wf_counts = await c.fetchall()

        pending = 0
        approved = 0
        rejected = 0
        for row in wf_counts:
            if row["approved"] == 0:
                pending = row["c"]
            elif row["approved"] == 1:
                approved = row["c"]
            elif row["approved"] == 2:
                rejected = row["c"]

        total_workflows = pending + approved + rejected

        total_checks = 0
        total_blocks = 0
        total_warnings = 0
        total_successes = 0

        if total_workflows == 0:
            token_savings = 0.0
            coverage = 0.0
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    async with db.execute("SELECT COUNT(*) FROM compatibility_reports") as c:
                        total_checks = (await c.fetchone())[0]
                    async with db.execute("SELECT COUNT(*) FROM compatibility_reports WHERE status='BLOCK'") as c:
                        total_blocks = (await c.fetchone())[0]
                    async with db.execute("SELECT COUNT(*) FROM compatibility_reports WHERE status='WARN'") as c:
                        total_warnings = (await c.fetchone())[0]
                    async with db.execute("SELECT COUNT(*) FROM compatibility_reports WHERE status='ALLOW'") as c:
                        total_successes = (await c.fetchone())[0]
            except Exception:
                pass
        else:
            # Calculate actual tokens using length heuristic
            async with aiosqlite.connect(DB_FILE) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT request_schema, response_schema FROM endpoints") as c:
                    eps = await c.fetchall()
                async with db.execute("SELECT generated_description FROM workflows") as c:
                    wfs = await c.fetchall()
                    
            raw_tokens = sum(len(str(ep["request_schema"] or "")) // 4 + len(str(ep["response_schema"] or "")) // 4 for ep in eps)
            clustered_tokens = sum(len(str(wf["generated_description"] or "")) // 4 for wf in wfs)
            
            raw_tokens = max(raw_tokens, 1)
            token_savings = (1 - (clustered_tokens / raw_tokens)) * 100 if raw_tokens > clustered_tokens else 0.0
            
            async with aiosqlite.connect(DB_FILE) as db:
                async with db.execute("SELECT COUNT(*) FROM endpoints WHERE community_id IS NOT NULL") as c:
                    row = await c.fetchone()
                    clustered_endpoints = row[0] if row else 0
                
                # Fetch compatibility metrics
                async with db.execute("SELECT COUNT(*) FROM compatibility_reports") as c:
                    total_checks = (await c.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM compatibility_reports WHERE status='BLOCK'") as c:
                    total_blocks = (await c.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM compatibility_reports WHERE status='WARN'") as c:
                    total_warnings = (await c.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM compatibility_reports WHERE status='ALLOW'") as c:
                    total_successes = (await c.fetchone())[0]
            coverage = (clustered_endpoints / endpoint_count) * 100 if endpoint_count > 0 else 0.0

        lines = [
            "# HELP dell_mcp_endpoints_total Total number of ingested OpenAPI endpoints.",
            "# TYPE dell_mcp_endpoints_total gauge",
            f"dell_mcp_endpoints_total {endpoint_count}",
            "# HELP dell_mcp_workflows_total Total number of discovered workflows.",
            "# TYPE dell_mcp_workflows_total gauge",
            f"dell_mcp_workflows_total {total_workflows}",
            "# HELP dell_mcp_workflows_approved_total Total number of approved workflows.",
            "# TYPE dell_mcp_workflows_approved_total gauge",
            f"dell_mcp_workflows_approved_total {approved}",
            "# HELP dell_mcp_workflows_pending_total Total number of pending workflows.",
            "# TYPE dell_mcp_workflows_pending_total gauge",
            f"dell_mcp_workflows_pending_total {pending}",
            "# HELP dell_mcp_workflows_rejected_total Total number of rejected workflows.",
            "# TYPE dell_mcp_workflows_rejected_total gauge",
            f"dell_mcp_workflows_rejected_total {rejected}",
            "# HELP dell_mcp_token_savings_percent Estimated LLM context token savings percentage.",
            "# TYPE dell_mcp_token_savings_percent gauge",
            f"dell_mcp_token_savings_percent {token_savings:.2f}",
            "# HELP dell_mcp_clustering_coverage_percent Percentage of endpoints successfully clustered.",
            "# TYPE dell_mcp_clustering_coverage_percent gauge",
            f"dell_mcp_clustering_coverage_percent {coverage:.2f}",
            "# HELP dell_mcp_compatibility_checks_total Total validation checks executed.",
            "# TYPE dell_mcp_compatibility_checks_total counter",
            f"dell_mcp_compatibility_checks_total {total_checks}",
            "# HELP dell_mcp_compatibility_blocks_total Total validation executions blocked.",
            "# TYPE dell_mcp_compatibility_blocks_total counter",
            f"dell_mcp_compatibility_blocks_total {total_blocks}",
            "# HELP dell_mcp_compatibility_warnings_total Total validation warnings raised.",
            "# TYPE dell_mcp_compatibility_warnings_total counter",
            f"dell_mcp_compatibility_warnings_total {total_warnings}",
            "# HELP dell_mcp_compatibility_successes_total Total validation checks successfully allowed.",
            "# TYPE dell_mcp_compatibility_successes_total counter",
            f"dell_mcp_compatibility_successes_total {total_successes}"
        ]

        # Fetch cache metrics
        from src.core.compatibility.sources import get_cache_metrics
        hits, misses = get_cache_metrics()
        lines.extend([
            "# HELP dell_mcp_facts_cache_hits_total Total facts cache hits.",
            "# TYPE dell_mcp_facts_cache_hits_total counter",
            f"dell_mcp_facts_cache_hits_total {hits}",
            "# HELP dell_mcp_facts_cache_misses_total Total facts cache misses.",
            "# TYPE dell_mcp_facts_cache_misses_total counter",
            f"dell_mcp_facts_cache_misses_total {misses}"
        ])

        return PlainTextResponse("\n".join(lines) + "\n")
    except Exception as err:
        logger.error(f"Prometheus metrics generation failed: {err}")
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/v1/workflows/{workflow_id}/export/ansible")
async def export_workflow_ansible(workflow_id: str):
    import yaml
    from fastapi.responses import PlainTextResponse
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
            ) as c:
                wf = await c.fetchone()

            if not wf:
                raise HTTPException(status_code=404, detail="Workflow not found")

            # Load steps
            async with db.execute(
                "SELECT * FROM endpoint_steps WHERE workflow_id = ? ORDER BY step_order",
                (workflow_id,),
            ) as c:
                steps = await c.fetchall()

        from src.core.compatibility.ansible_enricher import AnsiblePlaybookEnricher
        tasks = AnsiblePlaybookEnricher.enrich_playbook_tasks(steps)

        playbook = [
            {
                "name": f"Dell MCP Workflow Playbook: {wf['display_name']}",
                "hosts": "idrac_servers",
                "gather_facts": False,
                "vars": {
                    "idrac_ip": "192.168.1.100",
                    "idrac_user": "root",
                    "idrac_password": "calvin"
                },
                "tasks": tasks
            }
        ]

        yaml_content = yaml.dump(playbook, sort_keys=False)
        return PlainTextResponse(
            yaml_content,
            headers={
                "Content-Disposition": f"attachment; filename=workflow_{wf['system_name']}.yml"
            }
        )
    except Exception as err:
        logger.error(f"Ansible export failed: {err}")
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


@app.get("/api/v1/workflows/{workflow_id}/compatibility")
async def get_workflow_compatibility(workflow_id: str, target_ip: Optional[str] = None):
    try:
        # 1. Fetch workflow and steps from database
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)) as c:
                wf = await c.fetchone()
            if not wf:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            async with db.execute("SELECT * FROM endpoint_steps WHERE workflow_id = ? ORDER BY step_order", (workflow_id,)) as c:
                steps_rows = await c.fetchall()
        
        # Convert steps to matching format
        from pydantic import BaseModel
        class TempStep(BaseModel):
            operation_id: str
            method: str
            url: str
        
        steps = [
            TempStep(operation_id=r["operation_id"], method=r["method"], url=r["url"])
            for r in steps_rows
        ]
        
        # 2. Get target facts (from cache or static provider)
        ip = target_ip or "192.168.0.120"
        from src.core.compatibility.sources import CachedFactsProvider, StaticFactsProvider
        try:
            facts = await CachedFactsProvider().get_device_facts(ip)
        except Exception:
            facts = await StaticFactsProvider().get_device_facts(ip)
            
        # 3. Validate
        from src.core.compatibility.repository import CompatibilityRepository
        from src.core.compatibility.engine import CompatibilityEngine
        repo = CompatibilityRepository()
        engine = CompatibilityEngine(repo)
        report = await engine.validate_workflow(workflow_id, steps, facts)
        
        # Build dependency DAG visualization string
        dag = await engine.dag_engine.build_dependencies_dag()
        mermaid_diagram = engine.dag_engine.generate_mermaid_diagram(dag)
        
        return {
            "workflowId": workflow_id,
            "displayName": wf["display_name"],
            "status": report.status.value,
            "compatibilityScore": report.compatibility_score,
            "riskScore": report.risk_score,
            "blastRadius": report.blast_radius,
            "confidenceScore": report.confidence_score,
            "findings": [f.model_dump() for f in report.findings],
            "violations": [v.model_dump() for v in report.violations],
            "dependencyMermaid": mermaid_diagram,
            "timestamp": report.timestamp.isoformat()
        }
    except Exception as err:
        logger.error(f"Failed to calculate workflow compatibility: {err}")
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/v1/compatibility/rules")
async def get_compatibility_rules():
    try:
        from src.core.compatibility.repository import CompatibilityRepository
        repo = CompatibilityRepository()
        rules = await repo.get_active_rules()
        return rules
    except Exception as err:
        logger.error(f"Failed to fetch rules: {err}")
        raise HTTPException(status_code=500, detail=str(err))


class CreateRulePayload(BaseModel):
    id: str
    rule_name: str
    rule_type: str
    domain: str
    risk_score: int
    rule_config: str
    created_by: str = "admin"
    change_reason: str = "Created via API"


@app.post("/api/v1/compatibility/rules", dependencies=[Depends(get_api_key)])
async def create_compatibility_rule(payload: CreateRulePayload):
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                """
                INSERT INTO compatibility_rules (id, rule_name, rule_type, domain, rule_version, effective_from, created_by, change_reason, rule_config)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    payload.id,
                    payload.rule_name,
                    payload.rule_type,
                    payload.domain,
                    datetime.now(timezone.utc).isoformat(),
                    payload.created_by,
                    payload.change_reason,
                    payload.rule_config
                )
            )
            await db.commit()
        return {"status": "created", "rule_id": payload.id}
    except Exception as err:
        logger.error(f"Failed to create rule: {err}")
        raise HTTPException(status_code=500, detail=str(err))


@app.get("/api/v1/workflows/{workflow_id}/explainability")
async def get_workflow_explainability(workflow_id: str, target_ip: Optional[str] = None):
    try:
        # 1. Fetch workflow and steps from database
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)) as c:
                wf = await c.fetchone()
            if not wf:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            async with db.execute("SELECT * FROM endpoint_steps WHERE workflow_id = ? ORDER BY step_order", (workflow_id,)) as c:
                steps_rows = await c.fetchall()
        
        # Convert steps to TempStep
        from pydantic import BaseModel
        class TempStep(BaseModel):
            operation_id: str
            method: str
            url: str
        
        steps = [
            TempStep(operation_id=r["operation_id"], method=r["method"], url=r["url"])
            for r in steps_rows
        ]
        
        # 2. Get target facts (from cache or static provider)
        ip = target_ip or "192.168.0.120"
        from src.core.compatibility.sources import CachedFactsProvider, StaticFactsProvider
        try:
            facts = await CachedFactsProvider().get_device_facts(ip)
        except Exception:
            facts = await StaticFactsProvider().get_device_facts(ip)
            
        # 3. Validate
        from src.core.compatibility.repository import CompatibilityRepository
        from src.core.compatibility.engine import CompatibilityEngine
        repo = CompatibilityRepository()
        engine = CompatibilityEngine(repo)
        report = await engine.validate_workflow(workflow_id, steps, facts)
        
        # Build dependency DAG visualization string
        dag = await engine.dag_engine.build_dependencies_dag()
        mermaid_diagram = engine.dag_engine.generate_mermaid_diagram(dag)
        
        # Build risk heatmap data (Risk vs Blast Radius)
        risk_heatmap = {
            "matrix": {
                "READ_ONLY": {"NODE": 10, "CHASSIS": 20, "RACK": 30, "CLUSTER": 40},
                "CONFIG_CHANGE": {"NODE": 50, "CHASSIS": 60, "RACK": 70, "CLUSTER": 80},
                "DESTRUCTIVE": {"NODE": 90, "CHASSIS": 95, "RACK": 98, "CLUSTER": 100}
            },
            "current_position": {
                "risk": report.risk_score,
                "blast_radius": report.blast_radius
            }
        }
        
        # Extrapolate unsupported models and remediation
        unsupported = []
        remediation = []
        for v in report.violations:
            if v.field_checked == "device_model":
                unsupported.append(v.actual_value)
            if v.remediation_step:
                remediation.append(v.remediation_step)
                
        from src.core.compatibility.models import GovernanceExplainabilityReport
        return GovernanceExplainabilityReport(
            workflow_id=workflow_id,
            workflow_display_name=wf["display_name"],
            compatibility_score=report.compatibility_score,
            overall_risk_level="DESTRUCTIVE" if report.risk_score >= 80 else ("CONFIG_CHANGE" if report.risk_score >= 40 else "READ_ONLY"),
            confidence_level=report.confidence_score,
            blast_radius=report.blast_radius,
            unsupported_models=unsupported,
            remediation_actions=remediation,
            risk_heatmap_data=risk_heatmap,
            dependency_graph_mermaid=mermaid_diagram
        )
    except Exception as err:
        logger.error(f"Failed to fetch explainability report: {err}")
        raise HTTPException(status_code=500, detail=str(err))
