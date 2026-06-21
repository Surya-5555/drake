import typer
from src.cli.theme import render_json, render_panel
from src.cli.components import (
    render_compatibility_cockpit,
    render_metrics_table,
    render_rules_tree,
)

app = typer.Typer(help="Compatibility Intelligence Layer")


@app.command("validate")
def compatibility_validate(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="ID of the workflow"),
    target_ip: str = typer.Option(
        "192.168.0.120", "--target-ip", "-t", help="Target iDRAC/server IP"
    ),
) -> None:
    """Perform pre-flight verification on a workflow against a target device."""
    wrapper = ctx.obj
    report, facts, dag_info = wrapper.container.compatibility_service.validate_workflow(
        workflow_id, target_ip
    )

    if wrapper.context.json_output:
        render_json(report)
    else:
        status_color = (
            "green"
            if report["status"] == "ALLOW"
            else ("yellow" if report["status"] == "WARN" else "red")
        )
        content = (
            f"[bold white]Status               :[/bold white] [{status_color}]{report['status']}[/{status_color}]\n"
            f"[bold white]Compatibility Score  :[/bold white] {report['compatibility_score']}%\n"
            f"[bold white]Risk Score           :[/bold white] {report['risk_score']}/100\n"
            f"[bold white]Blast Radius         :[/bold white] {report['blast_radius']}\n"
            f"[bold white]Confidence           :[/bold white] {report['confidence_score']}%"
        )
        # Using theme helper via render_panel
        from src.cli.theme import console

        console.print(
            render_panel(
                content, title=f"Validation Check: {workflow_id} -> {target_ip}"
            )
        )


@app.command("explain")
def compatibility_explain(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="ID of the workflow"),
) -> None:
    """Render the topological DAG dependency tree of rules checking the workflow."""
    wrapper = ctx.obj
    # Re-use validate_workflow to fetch DAG and rules relationships
    _, _, dag_info = wrapper.container.compatibility_service.validate_workflow(
        workflow_id, "192.168.0.120"
    )

    if wrapper.context.json_output:
        render_json(dag_info)
    else:
        tree = render_rules_tree(dag_info)
        from src.cli.theme import console

        console.print(tree)


@app.command("dashboard")
def compatibility_dashboard(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="ID of the workflow"),
    target_ip: str = typer.Option(
        "192.168.0.120", "--target-ip", "-t", help="Target iDRAC/server IP"
    ),
) -> None:
    """The executive decision cockpit verifying SAFE/BLOCKED deployment verdicts."""
    wrapper = ctx.obj
    report, facts, dag_info = wrapper.container.compatibility_service.validate_workflow(
        workflow_id, target_ip
    )

    if wrapper.context.json_output:
        render_json({"report": report, "facts": facts})
    else:
        render_compatibility_cockpit(report, facts, dag_info)


@app.command("rules")
def compatibility_rules(ctx: typer.Context) -> None:
    """Print the complete active compatibility rules catalog."""
    wrapper = ctx.obj
    rules = wrapper.container.compatibility_service.get_rules()

    if wrapper.context.json_output:
        render_json(rules)
    else:
        from rich.table import Table
        from src.cli.theme import console

        table = Table(title="Active Rules Catalog", border_style="cyan")
        table.add_column("Rule ID", style="bold cyan")
        table.add_column("Rule Name", style="white")
        table.add_column("Domain", style="yellow")
        table.add_column("Version", style="cyan")
        table.add_column("Effective From", style="gray")

        for r in rules:
            table.add_row(
                r["id"],
                r["rule_name"],
                r["domain"],
                str(r["rule_version"]),
                r["effective_from"],
            )
        console.print(table)


@app.command("device")
def compatibility_device(
    ctx: typer.Context, ip: str = typer.Argument(..., help="Target device IP")
) -> None:
    """Retrieve stateful cached facts for a specific datacenter node."""
    wrapper = ctx.obj
    facts = wrapper.container.compatibility_service.get_device_facts(ip)

    if wrapper.context.json_output:
        render_json(facts)
    else:
        render_metrics_table(facts)
