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
    """
    executor_type = os.getenv("DELL_EXECUTOR_TYPE", "httpx").lower()
    executor: BaseExecutor

    if executor_type == "omsdk":
        executor = DellOMSDKExecutor()
    else:
        # Default/Fallback to MockHTTPXExecutor
        mock_server_url = os.getenv("MOCK_SERVER_URL", "http://localhost:8000")
        executor = MockHTTPXExecutor(base_url=mock_server_url)

    return await executor.execute_workflow(workflow_name, params)


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
    async with async_session() as session:
        result = await session.execute(
            select(Workflow)
            .where(Workflow.approved == 1)
            .options(selectinload(Workflow.steps))
        )
        approved_wfs = result.scalars().all()

        for wf in approved_wfs:
            name = wf.workflow_name
            desc = wf.generated_description or f"Execute clustered workflow for {name}"
            param_names = list(extract_placeholders_from_steps(wf.steps))

            def make_tool(wf_name, wf_desc, p_names):
                import inspect
                
                async def dynamic_tool(**kwargs) -> dict:
                    return await execute_workflow_route(wf_name, kwargs)
                
                dynamic_tool.__name__ = wf_name
                dynamic_tool.__doc__ = wf_desc
                
                params = []
                for p in p_names:
                    params.append(inspect.Parameter(
                        name=p,
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        default="",
                        annotation=str
                    ))
                dynamic_tool.__signature__ = inspect.Signature(parameters=params)  # type: ignore
                return dynamic_tool

            dynamic_tool = make_tool(name, desc, param_names)
            mcp.add_tool(dynamic_tool)
            logger.info(
                f"Dynamically registered workflow tool: {name} with params: {param_names}"
            )


@mcp.tool()
async def get_proxy_status() -> Dict[str, Any]:
    """
    Retrieve diagnostics metadata on the status of the Workflow Proxy.
    """
    tools = await mcp.list_tools()
    wf_names = [t.name for t in tools if t.name not in {"get_proxy_status", "preview_workflow_steps"}]
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
            "name": wf.workflow_name,
            "simulated_api_calls": [
                {
                    "step_id": idx + 1,
                    "method": step.method,
                    "url": step.url,
                }
                for idx, step in enumerate(wf.steps)
            ]
        }


# Define FastAPI Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Lifespan startup: initializing database and loading approved tools...")
    await init_db()

    # Sync governance.db state (Leiden clusters) to mcp_proxy.db
    try:
        from src.core.database import sync_governance_to_mcp_proxy
        await sync_governance_to_mcp_proxy()
        logger.info("Successfully synchronized governance.db to mcp_proxy.db at startup.")
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
            if tool.name not in {"get_proxy_status", "preview_workflow_steps"}:
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
