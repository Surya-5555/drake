import json
import logging
import os
import re
import sys
from typing import Any, Dict, Set

# Ensure project root is in the python path for execution via CLI tools
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from dotenv import load_dotenv  # noqa: E402
from fastmcp import FastMCP  # noqa: E402
from src.proxy.executors import (  # noqa: E402
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
mcp = FastMCP("Dell Enterprise MCP Workflow Proxy")

# Resolve mapping JSON path
MAPPING_PATH = os.getenv(
    "DELL_WORKFLOW_MAPPING_PATH", "data/output/workflow_mapping.json"
)


def load_workflow_mappings() -> Dict[str, Any]:
    """
    Reads the workflow mappings from the SQLite database (approved only).
    Falls back to local JSON file (Contract B) if database is empty or unavailable.
    """
    try:
        from src.core.database import DB_FILE, get_workflows
        if DB_FILE.exists():
            approved = get_workflows(approved_only=True)
            if approved:
                steps_mapping = {}
                for wf in approved:
                    steps_mapping[wf["workflowName"]] = {
                        "name": wf["workflowName"],
                        "description": wf["generatedDescription"],
                        "steps": [
                            {
                                "step_id": idx + 1,
                                "name": ep["operationId"],
                                "method": ep["method"],
                                "url": ep["url"],
                                "params": {},
                            } for idx, ep in enumerate(wf["underlyingEndpoints"])
                        ]
                    }
                logger.info(f"Loaded {len(steps_mapping)} approved workflows from SQLite database.")
                return {"workflows": steps_mapping}
    except Exception as err:
        logger.warning(f"Failed to load workflows from SQLite: {err}. Falling back to JSON.")

    if not os.path.exists(MAPPING_PATH):
        logger.warning(
            f"Workflow mapping file not found at '{MAPPING_PATH}'. Using fallback."
        )
        return {
            "workflows": {
                "server_health_check": {
                    "name": "server_health_check",
                    "description": (
                        "Query hardware status and health summaries of a server."
                    ),
                    "steps": [],
                }
            }
        }
    with open(MAPPING_PATH, "r") as f:
        data: Dict[str, Any] = json.load(f)
        return data


async def execute_workflow_route(
    workflow_name: str, params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Routes execution to the designated executor selected by env configuration.

    Ensures asynchronous execution is decoupled from routing parameters.
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


def extract_placeholders(workflow_data: Dict[str, Any]) -> Set[str]:
    """
    Parses paths and parameters in steps to extract placeholders.
    """
    placeholders: Set[str] = set()

    def search(data: Any) -> None:
        if isinstance(data, str):
            for match in re.findall(r"\{([a-zA-Z0-9_]+)\}", data):
                placeholders.add(match)
        elif isinstance(data, dict):
            for k, v in data.items():
                search(k)
                search(v)
        elif isinstance(data, list):
            for item in data:
                search(item)

    for step in workflow_data.get("steps", []):
        search(step.get("url", ""))
        search(step.get("params", {}))

    return placeholders


# Load mappings
try:
    mappings = load_workflow_mappings()
    workflows = mappings.get("workflows", {})
except Exception as err:
    logger.error(f"Failed to load workflow mappings: {err}")
    workflows = {}

# Dynamic Tool Registration Loop
for name, data in workflows.items():
    desc = data.get("description", f"Execute clustered workflow for {name}")
    param_names = list(extract_placeholders(data))

    # Construct the function signature and execution parameters dynamically
    sig_parts = [f"{p}: str = ''" for p in param_names]
    sig = ", ".join(sig_parts)
    dict_content = ", ".join(f"'{p}': {p}" for p in param_names)

    code = f"""
async def {name}({sig}) -> dict:
    \"\"\"{desc}\"\"\"
    params = {{{dict_content}}}
    return await execute_workflow_route('{name}', params)
"""
    local_vars: Dict[str, Any] = {}
    global_vars = {"execute_workflow_route": execute_workflow_route}
    exec(code, global_vars, local_vars)

    dynamic_tool = local_vars[name]
    mcp.add_tool(dynamic_tool)
    logger.info(
        f"Dynamically registered workflow tool: {name} with params: {param_names}"
    )


@mcp.tool()
async def get_proxy_status() -> Dict[str, Any]:
    """
    Retrieve diagnostics metadata on the status of the Workflow Proxy.
    """
    return {
        "status": "online",
        "registered_workflows": list(workflows.keys()),
        "mapping_path": MAPPING_PATH,
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
    workflow_data = workflows.get(workflow_id)
    if not workflow_data:
        return {"error": f"Workflow '{workflow_id}' not found."}
    
    return {
        "workflow_id": workflow_id,
        "name": workflow_data.get("name", workflow_id),
        "simulated_api_calls": workflow_data.get("steps", [])
    }
