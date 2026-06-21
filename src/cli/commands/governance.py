import typer
from src.cli.theme import render_json, render_success
from src.cli.components import render_workflows_table, render_workflow_summary

app = typer.Typer(help="Human-in-the-Loop Governance console")


@app.command("pending")
def governance_pending(ctx: typer.Context) -> None:
    """List all workflows awaiting administrative audit and approval."""
    wrapper = ctx.obj
    wfs = wrapper.container.governance_service.get_pending()

    if wrapper.context.json_output:
        render_json(wfs)
    else:
        render_workflows_table(wfs, title="Workflows Pending Review")


@app.command("approved")
def governance_approved(ctx: typer.Context) -> None:
    """List all certified workflows approved for execution."""
    wrapper = ctx.obj
    wfs = wrapper.container.governance_service.get_approved()

    if wrapper.context.json_output:
        render_json(wfs)
    else:
        render_workflows_table(wfs, title="Certified Workflows")


@app.command("rejected")
def governance_rejected(ctx: typer.Context) -> None:
    """List all rejected workflows."""
    wrapper = ctx.obj
    wfs = wrapper.container.governance_service.get_rejected()

    if wrapper.context.json_output:
        render_json(wfs)
    else:
        render_workflows_table(wfs, title="Rejected Workflows")


@app.command("review")
def governance_review(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="ID of the workflow"),
) -> None:
    """Review detailed API steps, parameters, and metadata for a specific workflow."""
    wrapper = ctx.obj
    wf = wrapper.container.governance_service.review_workflow(workflow_id)

    if wrapper.context.json_output:
        render_json(wf)
    else:
        render_workflow_summary(wf)

        # Also render steps in review
        from rich.table import Table
        from src.cli.theme import console

        table = Table(title="Workflow Operational Steps", border_style="cyan")
        table.add_column("Order", style="cyan")
        table.add_column("Method", style="bold yellow")
        table.add_column("URL Path", style="white")
        table.add_column("Operation ID", style="gray")

        for step in wf.get("steps", []):
            table.add_row(
                str(step["step_order"]),
                step["method"],
                step["url"],
                step["operation_id"],
            )
        console.print(table)


@app.command("approve")
def governance_approve(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="ID of the workflow"),
) -> None:
    """Approve a pending workflow, certifying it for runtime execution."""
    wrapper = ctx.obj
    wrapper.container.governance_service.approve_workflow(workflow_id)

    if wrapper.context.json_output:
        render_json({"status": "approved", "workflow_id": workflow_id})
    else:
        render_success(
            f"Workflow '{workflow_id}' has been approved and registered as an MCP tool."
        )


@app.command("reject")
def governance_reject(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="ID of the workflow"),
    reason: str = typer.Option(
        "Violates datacenter safety policies", help="Rejection explanation reason"
    ),
) -> None:
    """Reject a workflow, blocking it from execution and registering a safety explanation."""
    wrapper = ctx.obj
    wrapper.container.governance_service.reject_workflow(workflow_id, reason)

    if wrapper.context.json_output:
        render_json(
            {"status": "rejected", "workflow_id": workflow_id, "reason": reason}
        )
    else:
        render_success(f"Workflow '{workflow_id}' rejected. Reason: {reason}")
