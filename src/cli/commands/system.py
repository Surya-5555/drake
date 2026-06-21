import typer
from src.cli.theme import render_json
from src.cli.components import render_topology_tree

app = typer.Typer(help="Platform system structures")


@app.command("topology")
def system_topology(ctx: typer.Context) -> None:
    """Print the complete datacenter subsystem topology mapping hierarchy."""
    wrapper = ctx.obj

    if wrapper.context.json_output:
        # For JSON output, return a simple static structural list
        topology = {
            "name": "Dell Enterprise MCP Proxy Datacenter",
            "layers": [
                {
                    "name": "Governance Layer",
                    "components": ["Policy Engine", "Risk Assessor"],
                },
                {
                    "name": "Compatibility Intelligence Layer",
                    "components": [
                        "Compatibility Engine",
                        "Dependency DAG Engine",
                        "Stateful Facts Cache",
                    ],
                },
                {
                    "name": "Runtime Orchestration",
                    "components": ["FastMCP SSE Server", "Workflow Execution Manager"],
                },
                {
                    "name": "Executors",
                    "components": ["Prism HTTPX Executor", "Dell OMSDK Executor"],
                },
            ],
        }
        render_json(topology)
    else:
        tree = render_topology_tree()
        from src.cli.theme import console

        console.print(tree)
