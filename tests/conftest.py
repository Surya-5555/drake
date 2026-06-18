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
