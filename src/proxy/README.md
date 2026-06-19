# Proxy Module

This module implements the runtime execution and human-in-the-loop governance layer of the Dell MCP Workflow Proxy.

## Modules

### Governance API (`api.py`)
Serves standard REST endpoints for the governance dashboard:
- Queries pipeline execution posture and endpoints metrics.
- Exposes editing, approval, and rejection hooks for discovered workflows.
- Dynamically outputs React Flow elements representing graph relationships.
- Logs events to the SQLite audit database and triggers proxy hot-reloads.

### FastMCP Server (`server.py`)
Exposes the Model Context Protocol runtime.
- Interacts with `workflow_mapping.json` to register workflow-level tools dynamically.
- Resolves placeholder arguments mapping to tool signatures for client execution.
- Routes execution requests asynchronously using decoupled backend executors.

### Executors (`executors/`)
Decoupled target engines (e.g. `MockHTTPXExecutor` for test beds, `DellOMSDKExecutor` for Redfish hardware access) conforming to the `BaseExecutor` contract interface.
