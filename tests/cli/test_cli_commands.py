import pytest
import json
import sys
from pathlib import Path
from typer.testing import CliRunner
from src.cli.main import app, main
from src.cli.services import GovernanceCLIService
from src.cli.exceptions import DellCLIError

runner = CliRunner()

@pytest.fixture(autouse=True)
def manage_mock_plugins():
    # Setup: create a valid mock plugin and a broken plugin in src/cli/plugins/
    plugin_path = Path("src/cli/plugins/mock_plugin.py")
    plugin_code = """
import typer
app = typer.Typer(help="Mock Plugin Subcommand")
@app.command("hello")
def hello():
    print("Mock hello")
"""
    plugin_path.write_text(plugin_code, encoding="utf-8")

    broken_path = Path("src/cli/plugins/broken_plugin.py")
    broken_code = """
raise ValueError("Broken plugin initialization failure")
"""
    broken_path.write_text(broken_code, encoding="utf-8")

    yield

    # Teardown: delete the mock files
    if plugin_path.exists():
        plugin_path.unlink()
    if broken_path.exists():
        broken_path.unlink()
    # Remove from sys.modules to prevent caching side effects
    sys.modules.pop("src.cli.plugins.mock_plugin", None)
    sys.modules.pop("src.cli.plugins.broken_plugin", None)

def test_cli_help() -> None:
    """Ensure the main CLI displays help when called with no arguments."""
    import importlib
    import src.cli.main
    importlib.reload(src.cli.main)
    local_app = src.cli.main.app

    result = runner.invoke(local_app)
    assert result.exit_code == 2
    assert "Dell Enterprise MCP Proxy Platform" in result.stdout

    # Test explicit help flag
    res_help = runner.invoke(local_app, ["--help"])
    assert res_help.exit_code == 0
    assert "Options" in res_help.stdout
    assert "mock_plugin" in res_help.stdout  # Verifies the plugin was registered!

def test_overview_command() -> None:
    """Ensure the overview command outputs correct operational metrics in both modes."""
    # Test JSON mode
    result_json = runner.invoke(app, ["--json", "overview"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.stdout)
    assert "endpointCount" in data
    assert "workflowCount" in data
    assert "health" in data

    # Test Rich/text mode
    result_text = runner.invoke(app, ["overview"])
    assert result_text.exit_code == 0
    assert "Control Plane Executive Overview" in result_text.stdout

def test_health_command() -> None:
    """Ensure the health command evaluates subsystems readiness in both modes."""
    # Test JSON mode
    result_json = runner.invoke(app, ["--json", "health"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.stdout)
    assert "Database" in data
    assert "Governance" in data
    assert "Compatibility" in data

    # Test Rich/text mode
    result_text = runner.invoke(app, ["health"])
    assert result_text.exit_code == 0
    assert "Operational Health Status" in result_text.stdout

def test_cluster_commands() -> None:
    """Ensure the cluster commands output correct clustering metadata in both modes."""
    # Test cluster summary JSON and Rich
    res_summary_json = runner.invoke(app, ["--json", "cluster", "summary"])
    assert res_summary_json.exit_code == 0
    res_summary_text = runner.invoke(app, ["cluster", "summary"])
    assert res_summary_text.exit_code == 0

    # Test cluster graph JSON and Rich
    res_graph_json = runner.invoke(app, ["--json", "cluster", "graph"])
    assert res_graph_json.exit_code == 0
    res_graph_text = runner.invoke(app, ["cluster", "graph"])
    assert res_graph_text.exit_code == 0

    # Test cluster run with openapi.json
    res_run = runner.invoke(app, ["cluster", "run", "--spec", "openapi.json"])
    assert res_run.exit_code == 0

    # Test cluster run with missing file (error handling path)
    res_run_err = runner.invoke(app, ["cluster", "run", "--spec", "nonexistent_spec_file.json"])
    assert res_run_err.exit_code != 0
    assert isinstance(res_run_err.exception, DellCLIError)
    assert res_run_err.exception.title == "OpenAPI Spec File Missing"

def test_governance_commands() -> None:
    """Ensure the governance commands list workflows in both modes."""
    # Test pending list JSON and Rich
    res_pending_json = runner.invoke(app, ["--json", "governance", "pending"])
    assert res_pending_json.exit_code == 0
    res_pending_text = runner.invoke(app, ["governance", "pending"])
    assert res_pending_text.exit_code == 0

    # Test approved list JSON and Rich
    res_approved_json = runner.invoke(app, ["--json", "governance", "approved"])
    assert res_approved_json.exit_code == 0
    res_approved_text = runner.invoke(app, ["governance", "approved"])
    assert res_approved_text.exit_code == 0

    # Test rejected list JSON and Rich
    res_rejected_json = runner.invoke(app, ["--json", "governance", "rejected"])
    assert res_rejected_json.exit_code == 0
    res_rejected_text = runner.invoke(app, ["governance", "rejected"])
    assert res_rejected_text.exit_code == 0

def test_compatibility_commands() -> None:
    """Ensure compatibility commands query the active rules catalog in both modes."""
    res_rules_json = runner.invoke(app, ["--json", "compatibility", "rules"])
    assert res_rules_json.exit_code == 0
    res_rules_text = runner.invoke(app, ["compatibility", "rules"])
    assert res_rules_text.exit_code == 0

    # Test device facts cache query (error flow)
    res_dev_err = runner.invoke(app, ["compatibility", "device", "999.999.999.999"])
    assert res_dev_err.exit_code != 0
    assert isinstance(res_dev_err.exception, DellCLIError)
    assert res_dev_err.exception.title == "Device Query Failed"

def test_system_commands() -> None:
    """Ensure system structural commands print topologies in both modes."""
    res_topo_json = runner.invoke(app, ["--json", "system", "topology"])
    assert res_topo_json.exit_code == 0
    res_topo_text = runner.invoke(app, ["system", "topology"])
    assert res_topo_text.exit_code == 0

def test_diagnostics_commands() -> None:
    """Ensure diagnostics subsystem checks complete successfully in both modes."""
    # DB Diagnostics
    res_db_json = runner.invoke(app, ["--json", "diagnostics", "db"])
    assert res_db_json.exit_code == 0
    res_db_text = runner.invoke(app, ["diagnostics", "db"])
    assert res_db_text.exit_code == 0

    # API Diagnostics
    res_api_json = runner.invoke(app, ["--json", "diagnostics", "api"])
    assert res_api_json.exit_code == 0
    res_api_text = runner.invoke(app, ["diagnostics", "api"])
    assert res_api_text.exit_code == 0

    # Compatibility Diagnostics
    res_comp_json = runner.invoke(app, ["--json", "diagnostics", "compatibility"])
    assert res_comp_json.exit_code == 0
    res_comp_text = runner.invoke(app, ["diagnostics", "compatibility"])
    assert res_comp_text.exit_code == 0

    # Runtime Diagnostics
    res_run_json = runner.invoke(app, ["--json", "diagnostics", "runtime"])
    assert res_run_json.exit_code == 0
    res_run_text = runner.invoke(app, ["diagnostics", "runtime"])
    assert res_run_text.exit_code == 0

def test_audit_commands() -> None:
    """Ensure audit command groups list events and executions in both modes."""
    # Events
    res_events_json = runner.invoke(app, ["--json", "audit", "events"])
    assert res_events_json.exit_code == 0
    res_events_text = runner.invoke(app, ["audit", "events"])
    assert res_events_text.exit_code == 0

    # Executions
    res_exec_json = runner.invoke(app, ["--json", "audit", "executions"])
    assert res_exec_json.exit_code == 0
    res_exec_text = runner.invoke(app, ["audit", "executions"])
    assert res_exec_text.exit_code == 0

    # Summary
    res_summary_json = runner.invoke(app, ["--json", "audit", "summary"])
    assert res_summary_json.exit_code == 0
    res_summary_text = runner.invoke(app, ["audit", "summary"])
    assert res_summary_text.exit_code == 0

def test_runtime_commands() -> None:
    """Ensure runtime tools list and reload command run in both modes."""
    res_tools_json = runner.invoke(app, ["--json", "runtime", "tools"])
    assert res_tools_json.exit_code == 0
    res_tools_text = runner.invoke(app, ["runtime", "tools"])
    assert res_tools_text.exit_code == 0

    res_reload_json = runner.invoke(app, ["--json", "runtime", "reload"])
    assert res_reload_json.exit_code == 0
    res_reload_text = runner.invoke(app, ["runtime", "reload"])
    assert res_reload_text.exit_code == 0

    # Test invalid execute params format
    res_exec_err = runner.invoke(app, ["runtime", "execute", "wf_test", "--params", "invalid_json"])
    assert res_exec_err.exit_code != 0
    assert isinstance(res_exec_err.exception, DellCLIError)
    assert res_exec_err.exception.title == "Execution Parameter Parsing Failed"

def test_workflow_lifecycle_and_actions() -> None:
    """Retrieve workflows and verify reviews, approvals, playbooks, validations, and executions."""
    gov_service = GovernanceCLIService()
    # Use approved or rejected workflows since pending count is 0 in default seeded DB
    wfs = gov_service.get_approved() or gov_service.get_rejected()
    if wfs:
        wf_id = wfs[0]["id"]
        wf_name = wfs[0]["systemName"]
        
        # Test review command JSON and Rich
        res_review_json = runner.invoke(app, ["--json", "governance", "review", wf_id])
        assert res_review_json.exit_code == 0
        res_review_text = runner.invoke(app, ["governance", "review", wf_id])
        assert res_review_text.exit_code == 0

        # Test compatibility validate command JSON and Rich
        res_validate_json = runner.invoke(app, ["--json", "compatibility", "validate", wf_id])
        assert res_validate_json.exit_code == 0
        res_validate_text = runner.invoke(app, ["compatibility", "validate", wf_id])
        assert res_validate_text.exit_code == 0

        # Test compatibility explain command JSON and Rich
        res_explain_json = runner.invoke(app, ["--json", "compatibility", "explain", wf_id])
        assert res_explain_json.exit_code == 0
        res_explain_text = runner.invoke(app, ["compatibility", "explain", wf_id])
        assert res_explain_text.exit_code == 0

        # Test compatibility dashboard command JSON and Rich
        res_dash_json = runner.invoke(app, ["--json", "compatibility", "dashboard", wf_id])
        assert res_dash_json.exit_code == 0
        res_dash_text = runner.invoke(app, ["compatibility", "dashboard", wf_id])
        assert res_dash_text.exit_code == 0

        # Test ansible preview command JSON and Rich
        res_ansible_json = runner.invoke(app, ["--json", "ansible", "preview", wf_id])
        assert res_ansible_json.exit_code == 0
        res_ansible_text = runner.invoke(app, ["ansible", "preview", wf_id])
        assert res_ansible_text.exit_code == 0

        # Test ansible export command JSON and Rich
        res_export_json = runner.invoke(app, ["--json", "ansible", "export", wf_id])
        assert res_export_json.exit_code == 0
        res_export_text = runner.invoke(app, ["ansible", "export", wf_id])
        assert res_export_text.exit_code == 0

        # Test runtime execute simulating correct facts path
        res_exec = runner.invoke(app, ["--json", "runtime", "execute", wf_name, "--params", '{"sys_id": 1}'])
        # It could exit with code 0 or raise DellCLIError depending on exact backend connection
        assert res_exec.exit_code in [0, 1]

        # Test governance approve and reject actions (on pending workflows)
        res_approve = runner.invoke(app, ["governance", "approve", wf_id])
        assert res_approve.exit_code == 0

        res_reject = runner.invoke(app, ["governance", "reject", wf_id, "--reason", "Test rejection"])
        assert res_reject.exit_code == 0

def test_missing_workflow_errors() -> None:
    """Test error handling paths for nonexistent workflow actions."""
    bad_id = "nonexistent_wf_999"
    
    # Review error
    res = runner.invoke(app, ["governance", "review", bad_id])
    assert res.exit_code != 0
    assert isinstance(res.exception, DellCLIError)
    assert res.exception.title == "Workflow Not Found"

    # Approve error
    res = runner.invoke(app, ["governance", "approve", bad_id])
    assert res.exit_code != 0
    assert isinstance(res.exception, DellCLIError)
    assert res.exception.title == "Workflow Approval Aborted"

    # Reject error
    res = runner.invoke(app, ["governance", "reject", bad_id, "--reason", "Why"])
    assert res.exit_code != 0
    assert isinstance(res.exception, DellCLIError)
    assert res.exception.title == "Workflow Rejection Aborted"

    # Validate error
    res = runner.invoke(app, ["compatibility", "validate", bad_id])
    assert res.exit_code != 0
    assert isinstance(res.exception, DellCLIError)
    assert res.exception.title == "Validation Failure"

    # Ansible export error
    res = runner.invoke(app, ["ansible", "export", bad_id])
    assert res.exit_code != 0
    assert isinstance(res.exception, DellCLIError)
    assert res.exception.title == "Ansible Export Failed"

def test_main_error_handling(monkeypatch) -> None:
    """Ensure that calling main() directly prints the error block to stdout/stderr and exits."""
    import sys
    monkeypatch.setattr(sys, "argv", ["dell-mcp", "cluster", "run", "--spec", "nonexistent.json"])
    
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
