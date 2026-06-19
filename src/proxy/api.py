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

from src.ai_clustering.graph_clustering import build_relationship_graph
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


# Pydantic models for request bodies
class UpdateWorkflowPayload(BaseModel):
    workflowName: str
    generatedDescription: str


class RejectWorkflowPayload(BaseModel):
    reason: str


@app.get("/api/v1/overview")
async def get_overview() -> Dict[str, Any]:
    """Retrieve top-level statistics and stage statuses for the governance dashboard."""
    try:
        endpoints = get_all_endpoints()
        workflows = get_workflows()
        pipeline_statuses = get_pipeline_statuses()

        pending_count = sum(1 for w in workflows if w["approved"] == 0)
        approved_count = sum(1 for w in workflows if w["approved"] == 1)

        return {
            "endpointCount": len(endpoints),
            "workflowCount": len(workflows),
            "pendingReviewCount": pending_count,
            "registeredWorkflowCount": approved_count,
            "ingestionStatus": pipeline_statuses.get("ingestionStatus", "complete"),
            "graphStatus": pipeline_statuses.get("graphStatus", "complete"),
            "clusteringStatus": pipeline_statuses.get("clusteringStatus", "complete"),
            "mcpRuntimeStatus": pipeline_statuses.get("mcpRuntimeStatus", "complete"),
        }
    except Exception as err:
        logger.error(f"Overview failed: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {err}",
        )


@app.get("/api/v1/workflows/pending")
async def get_pending_workflows() -> List[Dict[str, Any]]:
    """Retrieve list of pending workflow clusters."""
    try:
        return get_workflows(pending_only=True)
    except Exception as err:
        logger.error(f"Pending workflows failed: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        )


@app.post("/api/v1/workflows/{workflow_id}/approve")
async def approve_workflow(workflow_id: str) -> Dict[str, str]:
    """Approve a workflow cluster to make it eligible for FastMCP registration."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        wf = cursor.fetchone()
        if not wf:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow '{workflow_id}' not found.",
            )

        conn.execute(
            "UPDATE workflows SET approved = 1, rejection_reason = NULL WHERE id = ?",
            (workflow_id,),
        )
        conn.commit()

    log_audit_event(
        "workflow_approved",
        "success",
        f"Approved workflow cluster '{wf['workflow_name']}' for FastMCP tool registration.",
        workflow_name=wf["workflow_name"],
        actor="admin",
    )

    # Syncapproved workflows to the shared workflow_mapping.json file
    sync_workflow_mappings()

    return {"status": "approved"}


@app.post("/api/v1/workflows/{workflow_id}/reject")
async def reject_workflow(workflow_id: str, payload: RejectWorkflowPayload) -> Dict[str, str]:
    """Reject a workflow cluster, preventing FastMCP registration."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        wf = cursor.fetchone()
        if not wf:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow '{workflow_id}' not found.",
            )

        conn.execute(
            "UPDATE workflows SET approved = 2, rejection_reason = ? WHERE id = ?",
            (payload.reason, workflow_id),
        )
        conn.commit()

    log_audit_event(
        "workflow_rejected",
        "success",
        f"Rejected workflow '{wf['workflow_name']}'. Reason: {payload.reason}",
        workflow_name=wf["workflow_name"],
        actor="admin",
    )

    # Syncapproved workflows to the shared workflow_mapping.json file
    sync_workflow_mappings()

    return {"status": "rejected"}


@app.patch("/api/v1/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, payload: UpdateWorkflowPayload) -> Dict[str, Any]:
    """Modify human-in-the-loop workflow name and generated description labels."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        wf = cursor.fetchone()
        if not wf:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow '{workflow_id}' not found.",
            )

        conn.execute(
            "UPDATE workflows SET workflow_name = ?, generated_description = ? WHERE id = ?",
            (payload.workflowName, payload.generatedDescription, workflow_id),
        )
        conn.commit()

    log_audit_event(
        "workflow_updated",
        "success",
        f"Updated name to '{payload.workflowName}' and description.",
        workflow_name=payload.workflowName,
        actor="admin",
    )

    # Syncapproved workflows to the shared workflow_mapping.json file
    sync_workflow_mappings()

    # Query updated workflow object
    workflows = get_workflows()
    updated_wf = next((w for w in workflows if w["id"] == workflow_id), None)
    if not updated_wf:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated workflow.",
        )
    return updated_wf


@app.post("/api/v1/mcp/reload")
async def reload_mcp() -> Dict[str, str]:
    """Force FastMCP proxy mappings sync and reload."""
    try:
        set_pipeline_status("mcpRuntimeStatus", "running")
        sync_workflow_mappings()
        set_pipeline_status("mcpRuntimeStatus", "complete")
        
        log_audit_event(
            "mcp_registered",
            "success",
            "FastMCP runtime mappings synced and reload triggered.",
            actor="admin",
        )
        return {"status": "reloaded"}
    except Exception as err:
        set_pipeline_status("mcpRuntimeStatus", "error")
        log_audit_event(
            "mcp_registered",
            "error",
            f"FastMCP reload failed: {err}",
            actor="admin",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        )


@app.get("/api/v1/graph")
async def get_graph() -> Dict[str, Any]:
    """Generate React Flow graph topology representing endpoints, relationships, and clusters."""
    try:
        endpoints = get_all_endpoints()
        workflows = get_workflows()

        # Build NetworkX graph to extract edges
        G = build_relationship_graph(endpoints)

        # Format Nodes
        nodes = []
        for ep in endpoints:
            nodes.append({
                "id": ep["operation_id"],
                "method": ep["method"],
                "label": ep["path"],
                "communityId": ep["community_id"] or "unclustered",
            })

        # Format Edges
        edges = []
        for idx, (source, target) in enumerate(G.edges()):
            edges.append({
                "id": f"edge_{idx}",
                "source": source,
                "target": target,
            })

        # Format Communities
        communities = []
        for wf in workflows:
            communities.append({
                "id": wf["communityId"] or wf["id"],
                "workflowName": wf["workflowName"],
                "size": wf["clusterSize"],
                "confidence": wf["confidence"],
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "communities": communities,
        }
    except Exception as err:
        logger.error(f"Graph query failed: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        )


@app.get("/api/v1/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Query high-level governance and token saving metrics for charts visualization."""
    try:
        endpoints = get_all_endpoints()
        workflows = get_workflows()

        raw_endpoint_count = len(endpoints)
        workflow_count = len(workflows)

        if workflow_count == 0:
            reduction_ratio = 1.0
            clustering_coverage = 0.0
            token_savings = 0.0
        else:
            reduction_ratio = round(raw_endpoint_count / workflow_count, 1)
            
            # Clustering coverage: endpoints that are associated with a workflow cluster
            clustered_endpoints = sum(1 for ep in endpoints if ep["community_id"] is not None)
            clustering_coverage = round((clustered_endpoints / raw_endpoint_count) * 100, 1)

            # Token savings: custom architected formula comparing raw tool descriptors vs workflow tools
            # Raw: ~400 tokens/endpoint. Clustered workflow: ~200 tokens/workflow.
            raw_tokens = raw_endpoint_count * 400
            clustered_tokens = workflow_count * 200
            token_savings = round((1 - (clustered_tokens / raw_tokens)) * 100, 1) if raw_tokens > 0 else 0.0

        approved_count = sum(1 for w in workflows if w["approved"] == 1)
        rejected_count = sum(1 for w in workflows if w["approved"] == 2)
        pending_count = sum(1 for w in workflows if w["approved"] == 0)

        # Build workflow distribution: endpoint counts per workflow
        distribution = []
        for wf in workflows:
            distribution.append({
                "workflowName": wf["workflowName"],
                "endpointCount": wf["clusterSize"],
            })

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        )


@app.get("/api/v1/audit/events")
async def get_audit_events() -> List[Dict[str, Any]]:
    """Retrieve the event history logs."""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM audit_events ORDER BY timestamp DESC")
            events = []
            for row in cursor.fetchall():
                events.append({
                    "id": row["id"],
                    "eventType": row["event_type"],
                    "status": row["status"],
                    "workflowName": row["workflow_name"],
                    "description": row["description"],
                    "actor": row["actor"],
                    "timestamp": row["timestamp"],
                })
            return events
    except Exception as err:
        logger.error(f"Audit events query failed: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err),
        )


def sync_workflow_mappings() -> None:
    """
    Serializes approved workflows to the shared JSON file.
    Only approved (status = 1) workflows are written out.
    """
    try:
        approved_workflows = get_workflows(approved_only=True)
        
        steps_mapping = {}
        for wf in approved_workflows:
            name = wf["workflowName"]
            # Find the underlying endpoints path parameters to map steps
            steps = []
            with get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM endpoints WHERE community_id = ?",
                    (wf["communityId"],),
                )
                endpoints = cursor.fetchall()
                for idx, ep in enumerate(endpoints):
                    steps.append({
                        "step_id": idx + 1,
                        "name": ep["operation_id"],
                        "method": ep["method"],
                        "path": ep["path"],
                        "params": {},  # Populated dynamically by proxy runtime
                    })
            
            steps_mapping[name] = {
                "name": name,
                "description": wf["generatedDescription"],
                "steps": steps,
            }
            
        output_path = Path(__file__).resolve().parent.parent.parent / "data" / "output" / "workflow_mapping.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump({"workflows": steps_mapping}, f, indent=2)
            
        logger.info(f"Synchronized {len(approved_workflows)} approved workflows to {output_path}")
    except Exception as err:
        logger.error(f"Syncing workflow mappings failed: {err}")
