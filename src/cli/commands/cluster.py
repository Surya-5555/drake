import typer
from pathlib import Path
from src.cli.theme import render_json, render_success
from src.cli.components import status_spinner, render_metrics_table

app = typer.Typer(help="AI Ingestion and Clustering Engine")


@app.command("run")
def run_cluster(
    ctx: typer.Context,
    spec: str = typer.Option("openapi.json", help="Path to OpenAPI spec YAML/JSON"),
) -> None:
    """Ingest OpenAPI paths and discover workflow clusters using Leiden clustering."""
    wrapper = ctx.obj
    verbose = wrapper.context.verbose

    with status_spinner("Analyzing spec and partitioning resource communities"):
        stats = wrapper.container.cluster_service.run_clustering(Path(spec), verbose)

    if wrapper.context.json_output:
        render_json(stats)
    else:
        render_success(
            "Spec analysis completed. Discovered communities saved to governance.db."
        )
        if verbose:
            render_metrics_table(stats)


@app.command("summary")
def cluster_summary(ctx: typer.Context) -> None:
    """Display high-level operational statistics on discovered workflow clusters."""
    wrapper = ctx.obj
    summary = wrapper.container.cluster_service.get_summary()

    if wrapper.context.json_output:
        render_json(summary)
    else:
        render_metrics_table(summary)


@app.command("graph")
def cluster_graph(ctx: typer.Context) -> None:
    """Print relationship node and edge totals for the derived schema graph."""
    wrapper = ctx.obj
    stats = wrapper.container.cluster_service.get_graph_stats()

    if wrapper.context.json_output:
        render_json(stats)
    else:
        render_metrics_table(stats)
