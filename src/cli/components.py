from contextlib import contextmanager
from typing import Any, Dict, List
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.columns import Columns
from src.cli.theme import console, get_symbols


@contextmanager
def status_spinner(msg: str) -> Any:
    """Context manager exposing a styled status spinner for long-running operations."""
    with console.status(f"[cyan]{msg}...[/cyan]", spinner="dots") as status:
        yield status


def render_platform_overview_dashboard(metrics: Dict[str, Any]) -> None:
    """Renders the executive overview dashboard."""
    # Platform status card
    status_table = Table(title="Platform Status", border_style="cyan", show_header=True)
    status_table.add_column("Subsystem", style="white")
    status_table.add_column("Status", style="bold")

    health = metrics.get("health", {})
    for subsystem, state in health.items():
        color = "green" if state == "HEALTHY" else "red"
        status_table.add_row(subsystem, f"[{color}]{state}[/{color}]")

    # Workflow metrics table
    wf_table = Table(
        title="Workflow Distribution", border_style="cyan", show_header=True
    )
    wf_table.add_column("Metric", style="white")
    wf_table.add_column("Count", style="cyan")

    wf_table.add_row("Total Workflows", str(metrics.get("workflowCount", 0)))
    wf_table.add_row("Approved Workflows", str(metrics.get("approvedCount", 0)))
    wf_table.add_row("Pending Workflows", str(metrics.get("pendingCount", 0)))
    wf_table.add_row("Rejected Workflows", str(metrics.get("rejectedCount", 0)))

    # Metrics
    metrics_table = Table(
        title="Operational Metrics", border_style="cyan", show_header=True
    )
    metrics_table.add_column("Metric", style="white")
    metrics_table.add_column("Value", style="cyan")
    metrics_table.add_row(
        "Total Endpoints Ingested", str(metrics.get("endpointCount", 0))
    )
    metrics_table.add_row(
        "Compatibility Rules Active", str(metrics.get("compatibilityRulesCount", 0))
    )
    metrics_table.add_row(
        "Device Inventory Count", str(metrics.get("cachedDevicesCount", 0))
    )
    metrics_table.add_row("Recent Executions", str(metrics.get("executionCount", 0)))
    metrics_table.add_row(
        "Validation Violations Blocked", str(metrics.get("violationsCount", 0))
    )

    console.print(
        Panel(
            Columns([status_table, wf_table, metrics_table], padding=4),
            title="[bold cyan]Dell Enterprise MCP Proxy Control Plane Executive Overview[/bold cyan]",
            border_style="cyan",
        )
    )


def render_health_matrix(health_status: Dict[str, str]) -> None:
    """Renders the systems readiness and health diagnostics card."""
    table = Table(
        title="System Health Directory", show_header=True, border_style="cyan"
    )
    table.add_column("Service Component", style="white")
    table.add_column("Status Assessment", style="bold")

    for comp, status in health_status.items():
        color = "green" if status == "HEALTHY" else "red"
        table.add_row(comp, f"[{color}]{status}[/{color}]")

    console.print(
        Panel(
            table,
            title="[bold green]Operational Health Status[/bold green]",
            border_style="green",
        )
    )


def render_metrics_table(metrics: Dict[str, Any]) -> None:
    """Generic table renderer for pipeline performance & statistics."""
    table = Table(show_header=True, border_style="cyan")
    table.add_column("Metric Property", style="white")
    table.add_column("Value", style="cyan")
    for k, v in metrics.items():
        table.add_row(str(k), str(v))
    console.print(table)


def render_workflow_summary(wf: Dict[str, Any]) -> None:
    """Renders visual panel card for workflow cluster details."""
    status_map = {
        0: "[amber]PENDING[/amber]",
        1: "[green]APPROVED[/green]",
        2: "[red]REJECTED[/red]",
    }
    status_str = status_map.get(wf.get("approved", 0), "[white]UNKNOWN[/white]")

    content = (
        f"[bold white]ID:[/bold white] {wf.get('id')}\n"
        f"[bold white]System Name:[/bold white] {wf.get('systemName')}\n"
        f"[bold white]Display Name:[/bold white] {wf.get('displayName')}\n"
        f"[bold white]Risk Level:[/bold white] {wf.get('riskLevel')}\n"
        f"[bold white]Cluster Size:[/bold white] {wf.get('clusterSize')}\n"
        f"[bold white]Confidence:[/bold white] {wf.get('confidence')}\n"
        f"[bold white]Approval State:[/bold white] {status_str}\n"
        f"[bold white]Description:[/bold white] {wf.get('generatedDescription')}"
    )
    if wf.get("rejectionReason"):
        content += (
            f"\n[bold red]Rejection Reason:[/bold red] {wf.get('rejectionReason')}"
        )

    console.print(
        Panel(
            content,
            title=f"[cyan]Workflow: {wf.get('displayName')}[/cyan]",
            border_style="cyan",
        )
    )


def render_risk_summary(wf: Dict[str, Any]) -> None:
    """Display risk scoring, adjustments, and coefficients."""
    content = (
        f"[bold white]Workflow:[/bold white] {wf.get('displayName')} ({wf.get('id')})\n"
        f"[bold white]Risk Level:[/bold white] {wf.get('riskLevel')}\n"
        f"[bold white]Risk Score:[/bold white] {wf.get('riskScore', 0.0)}/100\n"
        f"[bold white]Governance Score:[/bold white] {wf.get('governanceScore', 100.0)}/100\n"
        f"[bold white]Policy Version:[/bold white] {wf.get('policyVersion', 'N/A')}"
    )
    console.print(
        Panel(
            content,
            title="[bold yellow]Governance Risk Assessment[/bold yellow]",
            border_style="amber",
        )
    )


def render_rules_tree(dag_nodes_edges: Any) -> Tree:
    """Converts a networkx DAG representation into a structured Rich Tree hierarchy."""
    nodes, edges = dag_nodes_edges

    # We construct a tree of dependencies
    root = Tree("[bold cyan]Compatibility Rules Dependency Hierarchies[/bold cyan]")
    # If no edges, just add all nodes as root level items
    if not edges:
        for node in nodes:
            name = node.get("rule_name", node.get("id"))
            root.add(f"[white]{name} ({node.get('domain')})[/white]")
        return root

    # Map rule ID to rule info
    rule_map = {node["id"]: node for node in nodes}

    # Build tree nodes dict
    tree_nodes = {}
    for rule_id, rule in rule_map.items():
        name = rule.get("rule_name", rule_id)
        tree_nodes[rule_id] = f"[white]{name} ({rule.get('domain')})[/white]"

    # If there are sources/targets, display tree structure
    # Simplify by showing active prerequisite relationships
    symbols = get_symbols()
    for u, v in edges:
        parent_name = rule_map.get(u, {}).get("rule_name", u)
        child_name = rule_map.get(v, {}).get("rule_name", v)
        node = root.add(f"[bold yellow]{parent_name}[/bold yellow]")
        node.add(f"[cyan]{symbols['REQUIRES_PREFIX']}{child_name}[/cyan]")

    return root


def render_compatibility_cockpit(
    report: Dict[str, Any], facts: Dict[str, Any], dag_info: Any
) -> None:
    """Renders the final operator decision deck cockpit."""
    title = "[bold cyan]COMPATIBILITY COCKPIT[/bold cyan]"

    # Verdict calculation
    is_safe = report.get("status") == "ALLOW"
    symbols = get_symbols()
    verdict = (
        f"[bold green]{symbols['SAFE_VERDICT']}[/bold green]"
        if is_safe
        else f"[bold red]{symbols['BLOCK_VERDICT']}[/bold red]"
    )
    verdict_border = "green" if is_safe else "red"

    # Device facts formatting
    facts_str = (
        f"[bold white]Target IP :[/bold white] {facts.get('target_ip', 'Unknown')}\n"
        f"[bold white]Model     :[/bold white] {facts.get('device_model', 'Unknown')}\n"
        f"[bold white]BIOS      :[/bold white] {facts.get('bios_version', 'Unknown')}\n"
        f"[bold white]LC State  :[/bold white] {facts.get('lifecycle_controller_version', 'N/A')}\n"
        f"[bold white]Scan Time :[/bold white] {facts.get('last_scanned', 'N/A')}"
    )

    # Scores
    scores_str = (
        f"[bold white]Compatibility Score :[/bold white] {report.get('compatibility_score', 0)}%\n"
        f"[bold white]Risk Score          :[/bold white] {report.get('risk_score', 0)}/100\n"
        f"[bold white]Blast Radius        :[/bold white] {report.get('blast_radius', 'NODE')}\n"
        f"[bold white]Confidence Score    :[/bold white] {report.get('confidence_score', 0)}%"
    )

    # Violations
    violations_list = report.get("violations", [])
    if not violations_list:
        violations_str = "[bold green]None[/bold green]"
    else:
        v_lines = []
        for idx, v in enumerate(violations_list, 1):
            v_lines.append(
                f"{idx}. {v.get('field_checked')}: expected {v.get('expected_value')}, found {v.get('actual_value')}\n   Remediation: {v.get('remediation_step')}"
            )
        violations_str = "\n".join(v_lines)

    # Build layout
    facts_panel = Panel(
        facts_str, title="[white]Target Device[/white]", border_style="cyan"
    )
    scores_panel = Panel(
        scores_str, title="[white]Validation Scores[/white]", border_style="cyan"
    )
    violations_panel = Panel(
        violations_str,
        title="[white]Violations[/white]",
        border_style="cyan" if not violations_list else "red",
    )

    # Dependency Tree
    tree_widget = render_rules_tree(dag_info)
    tree_panel = Panel(
        tree_widget,
        title="[white]Prerequisites Dependencies[/white]",
        border_style="cyan",
    )

    # Verdict panel
    verdict_panel = Panel(
        verdict,
        title="[white]Final Execution Verdict[/white]",
        border_style=verdict_border,
        padding=(1, 4),
    )

    console.print(
        Panel(
            Group(
                Columns([facts_panel, scores_panel], padding=2),
                violations_panel,
                tree_panel,
                verdict_panel,
            ),
            title=title,
            border_style="cyan",
        )
    )


def render_workflows_table(wfs: List[Dict[str, Any]], title: str = "Workflows") -> None:
    """Renders a tabular layout of workflows."""
    table = Table(title=title, show_header=True, border_style="cyan")
    table.add_column("Workflow ID", style="bold cyan")
    table.add_column("System Name", style="white")
    table.add_column("Display Name", style="white")
    table.add_column("Risk Level", style="yellow")
    table.add_column("Cluster Size", style="cyan")
    table.add_column("Confidence", style="cyan")

    for wf in wfs:
        table.add_row(
            str(wf.get("id")),
            str(wf.get("systemName")),
            str(wf.get("displayName")),
            str(wf.get("riskLevel")),
            str(wf.get("clusterSize")),
            f"{wf.get('confidence', 0.0):.2f}",
        )
    console.print(table)


def render_topology_tree() -> Tree:
    """Renders the modular systems datacenter architecture tree topology."""
    root = Tree("[bold cyan]Dell Enterprise MCP Proxy Datacenter[/bold cyan]")
    gov = root.add("[bold white]Governance Layer[/bold white]")
    gov.add("[meta]Policy Engine[/meta]")
    gov.add("[meta]Risk Assessor[/meta]")

    comp = root.add("[bold white]Compatibility Intelligence Layer[/bold white]")
    comp.add("[meta]Compatibility Engine[/meta]")
    comp.add("[meta]Dependency DAG Engine[/meta]")
    comp.add("[meta]Stateful Facts Cache[/meta]")

    run = root.add("[bold white]Runtime Orchestration[/bold white]")
    run.add("[meta]FastMCP SSE Server[/meta]")
    run.add("[meta]Workflow Execution Manager[/meta]")

    execs = run.add("[bold white]Executors[/bold white]")
    execs.add("[meta]Prism HTTPX Executor[/meta]")
    execs.add("[meta]Dell OMSDK Executor[/meta]")
    return root
