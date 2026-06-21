import typer
from src.cli.theme import render_json
from src.cli.components import render_metrics_table

app = typer.Typer(help="Audit Ledger and Security Compliance logs")


@app.command("events")
def audit_events(ctx: typer.Context) -> None:
    """Print database log entries detailing approvals, rejections, and reloads."""
    wrapper = ctx.obj
    events = wrapper.container.audit_service.get_events()

    if wrapper.context.json_output:
        render_json(events)
    else:
        from rich.table import Table
        from src.cli.theme import console

        table = Table(title="Governance Security Audit Logs", border_style="cyan")
        table.add_column("Event ID", style="gray")
        table.add_column("Type", style="bold yellow")
        table.add_column("Status", style="cyan")
        table.add_column("Workflow", style="white")
        table.add_column("Actor", style="white")
        table.add_column("Timestamp", style="gray")

        for e in events:
            table.add_row(
                e["id"],
                e["event_type"],
                e["status"],
                e["workflow_name"] or "N/A",
                e["actor"],
                e["timestamp"],
            )
        console.print(table)


@app.command("executions")
def audit_executions(ctx: typer.Context) -> None:
    """Print the complete historical execution ledger for target nodes."""
    wrapper = ctx.obj
    executions = wrapper.container.audit_service.get_executions()

    if wrapper.context.json_output:
        render_json(executions)
    else:
        from rich.table import Table
        from src.cli.theme import console

        table = Table(title="Execution History Ledger", border_style="cyan")
        table.add_column("Job ID", style="cyan")
        table.add_column("Server IP", style="bold white")
        table.add_column("Workflow ID", style="white")
        table.add_column("Ledger Status", style="yellow")
        table.add_column("Timestamp", style="gray")

        for ex in executions:
            table.add_row(
                str(ex["id"]),
                ex["target_server_ip"],
                ex["workflow_id"],
                ex["status"],
                str(ex["timestamp"]),
            )
        console.print(table)


@app.command("summary")
def audit_summary(ctx: typer.Context) -> None:
    """Print aggregated counts for approvals, rejections, executions, and violations."""
    wrapper = ctx.obj
    metrics = wrapper.container.system_service.get_overview_metrics()

    summary = {
        "Total Approvals Registered": metrics.get("approvedCount", 0),
        "Total Rejections Logged": metrics.get("rejectedCount", 0),
        "Total Workflow Executions": metrics.get("executionCount", 0),
        "Total Security Blocks Triggered": metrics.get("violationsCount", 0),
    }

    if wrapper.context.json_output:
        render_json(summary)
    else:
        render_metrics_table(summary)
