import typer
import json
from src.cli.theme import render_json, render_success, render_panel
from src.cli.components import render_metrics_table, status_spinner

app = typer.Typer(help="FastMCP and Execution Engine")


@app.command("tools")
def runtime_tools(ctx: typer.Context) -> None:
    """List all registered dynamic tools exposed to FastMCP clients."""
    wrapper = ctx.obj
    tools = wrapper.container.runtime_service.get_registered_tools()

    if wrapper.context.json_output:
        render_json(tools)
    else:
        from rich.table import Table
        from src.cli.theme import console

        table = Table(title="FastMCP Registered Tools", border_style="cyan")
        table.add_column("Tool Name", style="bold cyan")
        table.add_column("Description", style="white")
        table.add_column("Risk Level", style="yellow")
        table.add_column("Steps", style="cyan")

        for t in tools:
            table.add_row(
                t["name"], t["description"], t["risk_level"], str(t["steps_count"])
            )
        console.print(table)


@app.command("reload")
def runtime_reload(ctx: typer.Context) -> None:
    """Warm-refresh the server tool mapping catalog after metadata changes."""
    wrapper = ctx.obj

    with status_spinner("Sending tool catalog reload signal to FastAPI Gateway"):
        res = wrapper.container.runtime_service.reload_mcp()

    if wrapper.context.json_output:
        render_json(res)
    else:
        render_success(f"Dynamic reload command executed. Result: {res.get('status')}")


@app.command("execute")
def runtime_execute(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="Workflow system name to execute"),
    target_ip: str = typer.Option(
        "127.0.0.1", "--target-ip", "-t", help="Target server IP address"
    ),
    params: str = typer.Option(
        "{}", "--params", "-p", help="JSON dictionary of execution parameters"
    ),
) -> None:
    """Simulate and execute workflow steps against a target PowerEdge server."""
    wrapper = ctx.obj

    try:
        dict_params = json.loads(params)
    except Exception:
        # Invalid parameters format
        from src.cli.exceptions import DellCLIError

        raise DellCLIError(
            title="Execution Parameter Parsing Failed",
            cause=f"Params string '{params}' is not valid JSON.",
            impact="Variables cannot be injected into step requests.",
            action="Provide double-quoted key-values: '{\"sys_id\": 5}'",
        )

    # Inject IP
    if "target_server_ip" not in dict_params:
        dict_params["target_server_ip"] = target_ip
        dict_params["server_ip"] = target_ip

    with status_spinner(
        f"Running pre-flight gates and executing workflow {workflow_id}"
    ):
        res = wrapper.container.runtime_service.execute_workflow(
            workflow_id, target_ip, dict_params
        )

    if wrapper.context.json_output:
        render_json(res)
    else:
        render_success(f"Workflow execution completed on target {target_ip}.")
        # Render timing, results, and pre-flight assessments
        assess = res.get("compatibility_assessment", {})
        if assess:
            content = (
                f"[bold white]Report Status        :[/bold white] {assess.get('status')}\n"
                f"[bold white]Compatibility Score  :[/bold white] {assess.get('compatibility_score')}%\n"
                f"[bold white]Risk Score           :[/bold white] {assess.get('risk_score')}/100\n"
                f"[bold white]Blast Radius         :[/bold white] {assess.get('blast_radius')}"
            )
            from src.cli.theme import console

            console.print(
                render_panel(content, title="Pre-Flight Validation Assessment")
            )

        # Render execution timing/steps
        stats = {k: v for k, v in res.items() if k != "compatibility_assessment"}
        render_metrics_table(stats)
