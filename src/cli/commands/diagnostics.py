import typer
from src.cli.theme import render_json, render_panel

app = typer.Typer(help="Subsystems diagnostics reports")


@app.command("db")
def diagnostics_db(ctx: typer.Context) -> None:
    """Run database health check and integrity diagnostics."""
    wrapper = ctx.obj
    res = wrapper.container.diagnostics_service.check_db()

    if wrapper.context.json_output:
        render_json(res)
    else:
        status = res.get("database_status", "UNKNOWN")
        color = "green" if status == "HEALTHY" else "red"
        content = (
            f"[bold white]Database Status    :[/bold white] [{color}]{status}[/{color}]\n"
            f"[bold white]Tables Present     :[/bold white] {res.get('tables_present', 0)}\n"
            f"[bold white]Registered Rules   :[/bold white] {res.get('rules_registered', 0)}\n"
            f"[bold white]Risk Profiles      :[/bold white] {res.get('risk_profiles_registered', 0)}\n"
            f"[bold white]Indexes Validated  :[/bold white] {res.get('indexes_present', False)}"
        )
        from src.cli.theme import console

        console.print(
            render_panel(
                content, title="Governance DB Health Assessment", border_style=color
            )
        )


@app.command("api")
def diagnostics_api(ctx: typer.Context) -> None:
    """Run API gateway network connection and port binding diagnostics."""
    wrapper = ctx.obj
    res = wrapper.container.diagnostics_service.check_api()

    if wrapper.context.json_output:
        render_json(res)
    else:
        status = res.get("api_gateway", "OFFLINE")
        color = "green" if status == "ONLINE" else "red"
        content = (
            f"[bold white]API Gateway Status :[/bold white] [{color}]{status}[/{color}]\n"
            f"[bold white]Port Listening     :[/bold white] {res.get('port_listening', 'N/A')}\n"
            f"[bold white]Metrics Endpoint   :[/bold white] {res.get('metrics_endpoint', 'N/A') if status == 'ONLINE' else 'UNREACHABLE'}\n"
            f"[bold white]Response Code      :[/bold white] {res.get('response_code', 'N/A')}"
        )
        if "error" in res:
            content += f"\n[bold red]Error Detail       :[/bold red] {res.get('error')}"
        from src.cli.theme import console

        console.print(
            render_panel(
                content, title="FastAPI Gateway Connection Check", border_style=color
            )
        )


@app.command("compatibility")
def diagnostics_compatibility(ctx: typer.Context) -> None:
    """Run compatibility engine index and cached schemas diagnostics."""
    wrapper = ctx.obj
    res = wrapper.container.diagnostics_service.check_compatibility()

    if wrapper.context.json_output:
        render_json(res)
    else:
        status = res.get("compatibility_layer", "DEGRADED")
        color = "green" if status == "HEALTHY" else "red"

        missing_tables = res.get("missing_tables", [])
        missing_str = ", ".join(missing_tables) if missing_tables else "None"

        content = (
            f"[bold white]Compatibility Layer Status :[/bold white] [{color}]{status}[/{color}]\n"
            f"[bold white]Missing Tables             :[/bold white] {missing_str}\n"
            f"[bold white]Risk Profiles Count        :[/bold white] {res.get('risk_profiles_count', 0)}\n"
            f"[bold white]Temporal Index Present     :[/bold white] {res.get('has_temporal_index', False)}\n"
            f"[bold white]Cached Devices             :[/bold white] {res.get('cached_devices', 0)}\n"
            f"[bold white]Rules Count                :[/bold white] {res.get('rules_count', 0)}\n"
            f"[bold white]Provider Health            :[/bold white] {res.get('provider_health', 'OFFLINE')}"
        )
        from src.cli.theme import console

        console.print(
            render_panel(
                content, title="Compatibility Layer Diagnostics", border_style=color
            )
        )


@app.command("runtime")
def diagnostics_runtime(ctx: typer.Context) -> None:
    """Run tool runtime registrations and API status diagnostics."""
    wrapper = ctx.obj
    res = wrapper.container.diagnostics_service.check_runtime()

    if wrapper.context.json_output:
        render_json(res)
    else:
        status = res.get("runtime_status", "DEGRADED")
        color = "green" if status == "HEALTHY" else "red"
        content = (
            f"[bold white]Runtime Status       :[/bold white] [{color}]{status}[/{color}]\n"
            f"[bold white]Registered MCP Tools :[/bold white] {res.get('registered_mcp_tools', 0)}\n"
            f"[bold white]Total Workflows      :[/bold white] {res.get('total_workflows', 0)}\n"
            f"[bold white]API Endpoint Status  :[/bold white] {res.get('api_endpoint', 'OFFLINE')}\n"
            f"[bold white]Port Listening       :[/bold white] {res.get('port_listening', 'N/A')}"
        )
        from src.cli.theme import console

        console.print(
            render_panel(
                content, title="FastMCP Tool Runtime Diagnostics", border_style=color
            )
        )
