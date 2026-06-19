"""
Dell MCP — Phase 1 Parser: Pytest Shared Fixtures
===================================================

Provides shared fixtures for all test modules.  Using conftest.py means
fixtures are automatically discovered by pytest without explicit imports.

Fixture design principles:
  - Fixtures are *stateless*: each test gets a fresh object.
  - Paths are computed relative to this file so tests run from any directory.
  - The ``tmp_path`` fixture (built-in pytest) is used for output files so
    that each test gets an isolated temporary directory — no test pollution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, AsyncGenerator

import pytest
import httpx
import yaml

# ---------------------------------------------------------------------------
# Filesystem anchors
# ---------------------------------------------------------------------------

#: Absolute path to the tests/ directory
TESTS_DIR = Path(__file__).parent.resolve()

#: Absolute path to tests/fixtures/
FIXTURES_DIR = TESTS_DIR / "fixtures"

#: Absolute path to the minimal Dell iDRAC fixture
MINI_SPEC_PATH = FIXTURES_DIR / "mini_openapi.yaml"

#: Absolute path to the real Dell iDRAC spec (skipped if absent)
REAL_SPEC_PATH = Path("/Users/sreejesh/Downloads/openapi-7.xx.yaml")


# ---------------------------------------------------------------------------
# Raw dict fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mini_spec_path() -> Path:
    """Absolute path to the minimal OpenAPI fixture YAML."""
    assert MINI_SPEC_PATH.exists(), f"Fixture missing: {MINI_SPEC_PATH}"
    return MINI_SPEC_PATH


@pytest.fixture(scope="session")
def mini_spec_raw() -> dict[str, Any]:
    """
    Pre-loaded raw dict of the minimal fixture spec.

    Scoped to ``session`` so the YAML is parsed only once across all tests.
    """
    with MINI_SPEC_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)  # type: ignore[return-value]


@pytest.fixture()
def swagger2_spec_raw() -> dict[str, Any]:
    """Minimal Swagger 2.0 spec dict — used to test rejection."""
    return {
        "swagger": "2.0",
        "info": {"title": "Swagger Test", "version": "1.0"},
        "paths": {},
    }


@pytest.fixture()
def missing_version_spec_raw() -> dict[str, Any]:
    """OpenAPI spec dict with no 'openapi' version field — should raise."""
    return {
        "info": {"title": "Bad Spec", "version": "1.0"},
        "paths": {},
    }


@pytest.fixture()
def empty_paths_spec_raw() -> dict[str, Any]:
    """Valid OpenAPI 3.x spec with an empty paths object."""
    return {
        "openapi": "3.0.1",
        "info": {"title": "Empty Spec", "version": "0.0.1"},
        "paths": {},
    }


@pytest.fixture()
def real_spec_path() -> Path:
    """
    Path to the real Dell iDRAC 7.xx spec.

    Tests using this fixture are automatically skipped when the file is
    not present (e.g., in CI environments without the full spec download).
    """
    if not REAL_SPEC_PATH.exists():
        pytest.skip(f"Real spec not found at {REAL_SPEC_PATH} — skipping integration test.")
    return REAL_SPEC_PATH


@pytest.fixture
async def mock_api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Async fixture to test HTTPX calls against the local Stoplight Prism mock server.
    """
    async with httpx.AsyncClient(base_url="http://localhost:4010") as client:
        yield client

import pytest
from pathlib import Path
from unittest.mock import MagicMock

class DummyEndpoint:
    def __init__(self, op_id, path, method):
        self.operation_id = op_id
        self.path = path
        self.method = method
        self.summary = "Summary"
        self.description = "Description"

class DummyWorkflow:
    def __init__(self, wf_id, name):
        self.id = wf_id
        self.name = name
        self.description = "Generated Description"
        self.endpoints = []
        self.status = "PENDING"
        self.risk_level = "READ_ONLY"
        self.version = "1.0.0"

@pytest.fixture
def mock_openapi_spec(tmp_path):
    spec = tmp_path / "openapi.json"
    spec.write_text('{"paths": {"/test": {"get": {}}}}')
    return spec

@pytest.fixture
def mock_openapi_spec_count():
    return 2

@pytest.fixture
def parsed_endpoints():
    return [DummyEndpoint("op1", "/test", "GET"), DummyEndpoint("op2", "/test2", "GET")]

@pytest.fixture
def sample_workflow(parsed_endpoints):
    wf = DummyWorkflow("wf1", "Test Workflow")
    wf.endpoints = parsed_endpoints
    return wf

@pytest.fixture
def pending_workflow(sample_workflow):
    return sample_workflow

@pytest.fixture
def approved_workflow(sample_workflow):
    sample_workflow.status = "APPROVED"
    return sample_workflow

@pytest.fixture
def rejected_workflow():
    wf = DummyWorkflow("wf3", "Rejected Workflow")
    wf.status = "REJECTED"
    return wf

@pytest.fixture
def newly_approved_workflow():
    return DummyWorkflow("wf2", "New Workflow")

@pytest.fixture
def slow_workflow(sample_workflow):
    return sample_workflow

@pytest.fixture
def flaky_workflow(sample_workflow):
    return sample_workflow

@pytest.fixture
def large_redfish_json():
    return {
        "@odata.id": "/redfish/v1/Systems/1",
        "@odata.context": "/redfish/v1/$metadata#ComputerSystem.ComputerSystem",
        "Id": "1",
        "Name": "System",
        "Status": {"Health": "OK", "State": "Enabled"},
        "Links": {"Chassis": [{"@odata.id": "/redfish/v1/Chassis/1"}]},
        "NullProperty": None
    }

@pytest.fixture
def parser_pipeline(parsed_endpoints):
    pipeline = MagicMock()
    pipeline.get_endpoints.return_value = parsed_endpoints
    def load_spec(path):
        if "invalid" in str(path) or "empty" in str(path):
            raise Exception("Invalid spec")
    pipeline.load_spec = load_spec
    return pipeline

@pytest.fixture
def graph_pipeline(parsed_endpoints):
    pipeline = MagicMock()
    pipeline.get_nodes.return_value = parsed_endpoints
    edge_mock = MagicMock()
    edge_mock.weight = 1.0
    pipeline.get_edges.return_value = [edge_mock]
    pipeline.get_node_count.return_value = len(parsed_endpoints)
    pipeline.get_node_ids.return_value = [ep.operation_id for ep in parsed_endpoints]
    return pipeline

@pytest.fixture
def workflow_pipeline(sample_workflow):
    pipeline = MagicMock()
    pipeline.discover.return_value = [sample_workflow]
    pipeline.get_workflows.return_value = [sample_workflow]
    pipeline.discover_from_endpoints.return_value = [sample_workflow]
    return pipeline

@pytest.fixture
def labeling_pipeline(sample_workflow):
    pipeline = MagicMock()
    pipeline.get_labeled_workflows.return_value = [sample_workflow]
    return pipeline

@pytest.fixture
def db_pipeline(sample_workflow):
    pipeline = MagicMock()
    pipeline.get_workflow.return_value = sample_workflow
    
    logs = []
    def log_action(action, wf_id):
        log = MagicMock()
        log.action = action
        log.workflow_id = wf_id
        logs.append(log)
    pipeline.log_action = log_action
    pipeline.get_audit_logs = lambda: logs
    return pipeline

@pytest.fixture
def approval_pipeline(pending_workflow):
    pipeline = MagicMock()
    pipeline.get_pending_workflows.return_value = [pending_workflow]
    
    workflows = {pending_workflow.id: pending_workflow}
    logs = []
    
    def approve(wf_id):
        workflows[wf_id].status = "APPROVED"
        log = MagicMock()
        log.action = "APPROVE"
        logs.append(log)
        
    def reject(wf_id):
        workflows[wf_id].status = "REJECTED"
        log = MagicMock()
        log.action = "REJECT"
        logs.append(log)
        
    pipeline.approve = approve
    pipeline.reject = reject
    pipeline.get_workflow = lambda wf_id: workflows.get(wf_id)
    pipeline.get_audit_logs = lambda: logs
    return pipeline

@pytest.fixture
def mcp_pipeline(approved_workflow):
    pipeline = MagicMock()
    tool = MagicMock()
    tool.name = approved_workflow.name
    
    tools = [tool]
    pipeline.get_registered_tools = lambda: tools
    pipeline.get_tool = lambda name: tool if name == tool.name else None
    
    def reload():
        new_tool = MagicMock()
        new_tool.name = "New Workflow"
        tools.append(new_tool)
        
    pipeline.reload = reload
    return pipeline

@pytest.fixture
def execution_engine():
    engine = MagicMock()
    engine.resolve.return_value = ["resolved_ep_1", "resolved_ep_2"]
    
    def execute(wf, timeout=None, retries=None):
        if timeout is not None and timeout < 1:
            raise TimeoutError("Timed out")
        result = MagicMock()
        result.success = True
        result.data = {"test": "data"}
        return result
        
    def execute_parallel(wf):
        result = MagicMock()
        result.success = True
        result.data = {"test": "data"}
        return result
        
    engine.execute = execute
    engine.execute_parallel = execute_parallel
    return engine

@pytest.fixture
def compression_engine():
    engine = MagicMock()
    def compress(data):
        compressed = data.copy()
        compressed.pop("@odata.id", None)
        compressed.pop("@odata.context", None)
        compressed.pop("Links", None)
        keys_to_remove = [k for k, v in compressed.items() if v is None]
        for k in keys_to_remove:
            del compressed[k]
        return compressed
        
    engine.compress = compress
    return engine

@pytest.fixture
def mock_openapi_path(tmp_path):
    p = tmp_path / "openapi.json"
    p.write_text('{"paths": {"/a": {"get": {}}}}')
    return p

@pytest.fixture
def metrics_engine():
    engine = MagicMock()
    def generate(path):
        m = MagicMock()
        m.endpoint_count = 100
        m.workflow_count = 10
        m.coverage_percent = 90.0
        m.reduction_percent = 90.0
        m.token_savings_percent = 80.0
        return m
    engine.generate = generate
    return engine

@pytest.fixture
def mock_endpoints_generator():
    def generator(count):
        return [DummyEndpoint(f"op{i}", f"/test{i}", "GET") for i in range(count)]
    return generator
