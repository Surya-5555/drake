import logging
import os
import re
import sys
import weakref
from contextlib import asynccontextmanager
from typing import Any, Dict, Set

# Ensure project root is in the python path for execution via CLI tools
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP
from mcp.server.session import ServerSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.core.database import (
    async_session,
    init_db,
    init_db_sync,
    Workflow,
    EndpointStep,
)
from src.proxy.executors import (
    BaseExecutor,
    DellOMSDKExecutor,
    MockHTTPXExecutor,
)

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dell_mcp_proxy")

# Initialize FastMCP Server
mcp = FastMCP("Dell Enterprise Proxy")

# Track active MCP server sessions for hot-reloading notification
active_sessions = weakref.WeakSet()

original_init = ServerSession.__init__


def tracked_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    active_sessions.add(self)


ServerSession.__init__ = tracked_init


async def execute_workflow_route(
    workflow_name: str, params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Routes execution to the designated executor selected by env configuration.
    Integrates pre-flight validation rules under the orchestrator WorkflowExecutionManager.
    """
    from src.core.compatibility.orchestrator import WorkflowExecutionManager
    manager = WorkflowExecutionManager()
    return await manager.execute_workflow_with_validation(workflow_name, params)


def extract_placeholders_from_steps(steps) -> Set[str]:
    """
    Parses URLs in steps to extract placeholders.
    """
    placeholders = set()
    for step in steps:
        if step.url:
            for match in re.findall(r"\{([a-zA-Z0-9_]+)\}", step.url):
                placeholders.add(match)
    return placeholders


async def load_approved_tools_from_db() -> None:
    """
    Queries the SQLite DB for workflows where status == 'approved',
    iterates through them, and registers them dynamically using mcp.add_tool().
    """
    import json
    from pydantic import create_model, Field
    from src.proxy.executors.httpx_executor import PrismExecutor, MockExecutor
    from src.proxy.executors.dell_omsdk_executor import DellOMSDKExecutor

    async with async_session() as session:
        result = await session.execute(
            select(Workflow)
            .where(Workflow.approved == 1)
            .options(selectinload(Workflow.steps))
        )
        approved_wfs = result.scalars().all()

        for wf in approved_wfs:
            name = wf.system_name

            # Build complete parameter signature from all steps
            all_params = {}
            schemas_doc = []

            for step in wf.steps:
                try:
                    req_params = json.loads(step.required_params) if step.required_params else []
                    for p in req_params:
                        p_name = p.get("name")
                        if p_name and p_name != "body":
                            # Map primitive types
                            p_type = str
                            if p.get("param_type") == "integer": p_type = int
                            elif p.get("param_type") == "boolean": p_type = bool
                            all_params[p_name] = (p_type, ... if p.get("required", True) else None)
                except Exception:
                    pass

                try:
                    if step.request_schema:
                        schema = json.loads(step.request_schema)
                        schemas_doc.append(
                            f"\nStep {step.step_order} ({step.method} {step.url}) Body Schema:\n"
                            f"{json.dumps(schema, indent=2)}"
                        )
                        # Extract top-level properties from schema and add to parameters
                        if schema.get("type") == "object" and "properties" in schema:
                            for prop, details in schema["properties"].items():
                                if prop not in all_params:
                                    all_params[prop] = (Any, None) # Allow passing any JSON structure for body params
                except Exception:
                    pass

            # Extend description with body schemas
            desc = wf.generated_description or f"Execute clustered workflow for {name}"
            if schemas_doc:
                desc += "\n\n### Required Request Body Structures:\n" + "\n".join(schemas_doc)

            # Use inspect.Signature to create dynamic kwargs
            import inspect
            def make_tool(wf_name, wf_desc, params_dict):
                async def dynamic_tool(**kwargs) -> dict:
                    return await execute_workflow_route(wf_name, kwargs)

                dynamic_tool.__name__ = wf_name
                dynamic_tool.__doc__ = wf_desc

                sig_params = []
                for k, (t, default) in params_dict.items():
                    sig_params.append(
                        inspect.Parameter(
                            name=k,
                            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            default=inspect.Parameter.empty if default is ... else default,
                            annotation=t,
                        )
                    )
                dynamic_tool.__signature__ = inspect.Signature(parameters=sig_params)
                dynamic_tool.__annotations__ = {k: t for k, (t, d) in params_dict.items()}
                dynamic_tool.__annotations__["return"] = dict
                return dynamic_tool

            dynamic_tool = make_tool(name, desc, all_params)
            mcp.add_tool(dynamic_tool)
            logger.info(f"Dynamically registered workflow tool: {name} with schema params: {list(all_params.keys())}")


@mcp.tool()
async def get_proxy_status() -> Dict[str, Any]:
    """
    Retrieve diagnostics metadata on the status of the Workflow Proxy.
    """
    tools = await mcp.list_tools()
    wf_names = [
        t.name
        for t in tools
        if t.name not in {"get_proxy_status", "preview_workflow_steps", "check_workflow_compatibility", "preview_compatibility_report"}
    ]
    return {
        "status": "online",
        "registered_workflows": wf_names,
        "executor_configured": os.getenv("DELL_EXECUTOR_TYPE", "httpx"),
    }


@mcp.tool()
async def preview_workflow_steps(workflow_id: str) -> Dict[str, Any]:
    """
    Acts as a 'Blast Radius Audit' tool.

    Satisfies strict enterprise compliance by allowing human admins to review
    API execution paths and simulate the exact granular API calls it is about
    to make before any potentially destructive actions occur.

    Args:
        workflow_id (str): The unique identifier of the workflow to preview.

    Returns:
        Dict[str, Any]: A simulated list of granular API calls for the requested workflow.
    """
    async with async_session() as session:
        result = await session.execute(
            select(Workflow)
            .where(Workflow.id == workflow_id)
            .options(selectinload(Workflow.steps))
        )
        wf = result.scalar_one_or_none()
        if not wf:
            return {"error": f"Workflow '{workflow_id}' not found."}

        return {
            "workflow_id": workflow_id,
            "name": wf.display_name,
            "simulated_api_calls": [
                {
                    "step_id": idx + 1,
                    "method": step.method,
                    "url": step.url,
                }
                for idx, step in enumerate(wf.steps)
            ],
        }


@mcp.tool()
async def check_workflow_compatibility(workflow_id: str, target_ip: str) -> Dict[str, Any]:
    """
    Evaluates real-time compatibility of a workflow against a specific target server IP.
    Fetches target configuration details and matches them against active rules catalog guidelines.
    """
    from src.core.compatibility.sources import CachedFactsProvider, StaticFactsProvider, RedfishFactsProvider
    from src.core.compatibility.repository import CompatibilityRepository
    from src.core.compatibility.engine import CompatibilityEngine
    from src.core.compatibility.models import BaseExplainabilityReport
    
    # 1. Fetch workflow steps
    async with async_session() as session:
        result = await session.execute(
            select(Workflow)
            .where(Workflow.id == workflow_id)
            .options(selectinload(Workflow.steps))
        )
        wf = result.scalar_one_or_none()
        if not wf:
            return {"error": f"Workflow '{workflow_id}' not found."}
        steps = wf.steps

    # 2. Query target device facts
    repo = CompatibilityRepository()
    engine = CompatibilityEngine(repo)
    
    try:
        provider = RedfishFactsProvider()
        facts = await provider.get_device_facts(target_ip)
        await repo.save_device_facts(facts)
    except Exception:
        try:
            facts = await CachedFactsProvider().get_device_facts(target_ip)
        except Exception:
            facts = await StaticFactsProvider().get_device_facts(target_ip)
            
    # 3. Perform validation
    report = await engine.validate_workflow(workflow_id, steps, facts)

    unsupported = [v.actual_value for v in report.violations if v.field_checked == "device_model"]
    remediation = [v.remediation_step for v in report.violations if v.remediation_step]
    
    explain_report = BaseExplainabilityReport(
        workflow_id=workflow_id,
        workflow_display_name=wf.display_name,
        compatibility_score=report.compatibility_score,
        overall_risk_level="DESTRUCTIVE" if report.risk_score >= 80 else ("CONFIG_CHANGE" if report.risk_score >= 40 else "READ_ONLY"),
        confidence_level=report.confidence_score,
        blast_radius=report.blast_radius,
        unsupported_models=unsupported,
        remediation_actions=remediation,
        risk_heatmap_data={}
    )

    return {
        "compatibility_summary": f"Status: {report.status.value}, Score: {report.compatibility_score}%",
        "explainability_summary": f"Verified workflow compliance for model '{facts.device_model}'.",
        "blast_radius_summary": f"Containment level: {explain_report.blast_radius}",
        "risk_summary": f"Risk rating: {explain_report.overall_risk_level} ({report.risk_score}/100)",
        "confidence_summary": f"Confidence index: {report.confidence_score}%",
        "explain_report": explain_report.model_dump(),
        "findings": [f.model_dump() for f in report.findings],
        "violations": [v.model_dump() for v in report.violations],
    }


@mcp.tool()
async def preview_compatibility_report(workflow_id: str) -> Dict[str, Any]:
    """
    Previews structural workflow compatibility risks and prerequisite dependency rules
    against a standard model baseline.
    """
    from src.core.compatibility.sources import StaticFactsProvider
    from src.core.compatibility.repository import CompatibilityRepository
    from src.core.compatibility.engine import CompatibilityEngine
    from src.core.compatibility.models import BaseExplainabilityReport

    # 1. Fetch workflow steps
    async with async_session() as session:
        result = await session.execute(
            select(Workflow)
            .where(Workflow.id == workflow_id)
            .options(selectinload(Workflow.steps))
        )
        wf = result.scalar_one_or_none()
        if not wf:
            return {"error": f"Workflow '{workflow_id}' not found."}
        steps = wf.steps

    repo = CompatibilityRepository()
    engine = CompatibilityEngine(repo)
    
    facts = await StaticFactsProvider().get_device_facts("192.168.0.120")
    report = await engine.validate_workflow(workflow_id, steps, facts)

    unsupported = [v.actual_value for v in report.violations if v.field_checked == "device_model"]
    remediation = [v.remediation_step for v in report.violations if v.remediation_step]
    
    explain_report = BaseExplainabilityReport(
        workflow_id=workflow_id,
        workflow_display_name=wf.display_name,
        compatibility_score=report.compatibility_score,
        overall_risk_level="DESTRUCTIVE" if report.risk_score >= 80 else ("CONFIG_CHANGE" if report.risk_score >= 40 else "READ_ONLY"),
        confidence_level=report.confidence_score,
        blast_radius=report.blast_radius,
        unsupported_models=unsupported,
        remediation_actions=remediation,
        risk_heatmap_data={}
    )

    return {
        "compatibility_summary": f"Status: {report.status.value}, Score: {report.compatibility_score}%",
        "explainability_summary": f"Verified workflow compliance for model '{facts.device_model}'.",
        "blast_radius_summary": f"Containment level: {explain_report.blast_radius}",
        "risk_summary": f"Risk rating: {explain_report.overall_risk_level} ({report.risk_score}/100)",
        "confidence_summary": f"Confidence index: {report.confidence_score}%",
        "explain_report": explain_report.model_dump(),
        "findings": [f.model_dump() for f in report.findings],
        "violations": [v.model_dump() for v in report.violations],
    }


# Define FastAPI Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Lifespan startup: initializing database and loading approved tools...")
    init_db_sync()
    await init_db()

    # Sync governance.db state (Leiden clusters) to mcp_proxy.db
    try:
        from src.core.database import sync_governance_to_mcp_proxy

        await sync_governance_to_mcp_proxy()
        logger.info(
            "Successfully synchronized governance.db to mcp_proxy.db at startup."
        )
    except Exception as e:
        logger.error(f"Failed to sync governance.db to mcp_proxy.db at startup: {e}")

    await load_approved_tools_from_db()
    yield
    # Shutdown actions
    logger.info("Lifespan shutdown complete.")


from fastapi.middleware.cors import CORSMiddleware
from src.proxy.api import app as api_app

# Initialize standard FastAPI app
app = FastAPI(
    title="Dell Enterprise MCP Proxy API Server",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def reload_mcp_tools():
    try:
        # Dynamically clear existing dynamic tools in the mcp instance
        tools = await mcp.list_tools()
        for tool in tools:
            if tool.name not in {"get_proxy_status", "preview_workflow_steps", "check_workflow_compatibility", "preview_compatibility_report"}:
                try:
                    mcp.local_provider.remove_tool(tool.name)
                    logger.info(f"Removed dynamic tool: {tool.name}")
                except Exception as e:
                    logger.warning(f"Error removing tool {tool.name}: {e}")

        # Re-run load_approved_tools_from_db()
        await load_approved_tools_from_db()

        # Notify connected MCP clients
        notified_count = 0
        for session in list(active_sessions):
            try:
                await session.send_tool_list_changed()
                notified_count += 1
                logger.info(f"Notified session {session} of tool list change.")
            except Exception as e:
                logger.warning(f"Failed to notify session: {e}")

        return {"status": "reloaded", "notified_clients": notified_count}
    except Exception as err:
        logger.exception("Reload failed")
        raise err


# Mount the MCP server to FastAPI using FastMCP's ASGI/SSE integration
app.mount("/mcp", mcp.http_app(transport="sse"))

# Expose reload callback to API app
api_app.state.mcp_reload = reload_mcp_tools

# Mount the governance API app
app.mount("/", api_app)
