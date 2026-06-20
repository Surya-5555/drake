import typer
from pathlib import Path
from src.cli.theme import render_json, render_success
from rich.syntax import Syntax

app = typer.Typer(help="Ansible Playbook Enrichment Exporter")


@app.command("preview")
def ansible_preview(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="ID of the workflow"),
) -> None:
    """Render the enriched YAML playbook configuration utilizing Rich syntax highlighting."""
    wrapper = ctx.obj
    res = wrapper.container.ansible_service.get_playbook(workflow_id)

    if wrapper.context.json_output:
        render_json(res)
    else:
        # Render using rich syntax
        from src.cli.theme import console

        yaml_content = res.get("yaml_content", "")
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)


@app.command("export")
def ansible_export(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="ID of the workflow"),
    output: str = typer.Option("", "--output", "-o", help="File path to write YAML to"),
) -> None:
    """Export the playbooks and prerequisite configuration settings to a local file."""
    wrapper = ctx.obj
    res = wrapper.container.ansible_service.get_playbook(workflow_id)
    yaml_content = res.get("yaml_content", "")

    if wrapper.context.json_output:
        render_json(res)
    else:
        if output:
            try:
                p = Path(output)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(yaml_content, encoding="utf-8")
                render_success(f"Ansible playbook exported successfully to '{output}'.")
            except Exception as e:
                from src.cli.exceptions import DellCLIError

                raise DellCLIError(
                    title="Export File Write Failed",
                    cause=str(e),
                    impact="Ansible playbook could not be saved to disk.",
                    action=f"Verify write permissions to the path '{output}'.",
                )
        else:
            # Print to stdout directly
            from src.cli.theme import console

            syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
            console.print(syntax)
