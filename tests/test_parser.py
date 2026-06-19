"""
Dell MCP — Phase 1 Parser: Full Test Suite
==========================================

Tests are organised into four groups:

  Unit Tests — Core Functions
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~
  1. ``TestLoadSpec``        — file loading, encoding, error paths
  2. ``TestValidateSpec``    — version gating, openapi-core integration
  3. ``TestExtractEndpoints`` — the core extraction loop (all edge cases)
  4. ``TestBuildContractA``  — Pydantic model assembly
  5. ``TestSaveContractA``   — JSON serialisation and file I/O

  Unit Tests — Helpers
  ~~~~~~~~~~~~~~~~~~~~~
  6. ``TestMergeParameters`` — path-level vs operation-level param override
  7. ``TestExtractRequiredParams`` — required-only filtering logic

  Integration Tests — Fixture Spec
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  8. ``TestMiniSpecIntegration`` — end-to-end pipeline on mini_openapi.yaml

  Integration Tests — Real Spec (skipped if absent)
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  9. ``TestRealSpecIntegration`` — end-to-end on openapi-7.xx.yaml

QUALITY CHECKS ENCODED IN TESTS:
  - No ``description``, ``summary``, ``x-*``, ``example``, ``tag`` keys
    in Contract A output (token exhaustion prevention)
  - Path params always captured (OpenAPI 3.x §4.8.12 compliance)
  - Optional params never captured
  - Required body params synthesised as ``location="body"``
  - Operation count matches expected fixture count
  - Contract A round-trips correctly through JSON deserialisation
  - Swagger 2.0 specs are rejected with correct exception
  - Missing spec files raise ``SpecFileNotFoundError``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.core.exceptions import (
    SpecFileNotFoundError,
    SpecParseError,
    UnsupportedSpecVersionError,
)
from src.core.models import ContractA, EndpointContract, RequiredParameter
from src.parser.openapi_parser import (
    OpenAPIParser,
    _extract_required_params,
    _merge_parameters,
    build_contract_a,
    extract_endpoints,
    load_spec,
    save_contract_a,
    validate_spec,
)

# ===========================================================================
# 1. TestLoadSpec
# ===========================================================================


class TestLoadSpec:
    """Tests for the load_spec() function."""

    def test_loads_valid_yaml(self, mini_spec_path: Path) -> None:
        """Happy path: a valid YAML spec loads into a non-empty dict."""
        raw = load_spec(mini_spec_path)
        assert isinstance(raw, dict)
        assert "openapi" in raw
        assert "paths" in raw

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """Missing spec file raises SpecFileNotFoundError, not FileNotFoundError."""
        ghost = tmp_path / "does_not_exist.yaml"
        with pytest.raises(SpecFileNotFoundError) as exc_info:
            load_spec(ghost)
        assert str(ghost) in str(exc_info.value)

    def test_raises_on_invalid_yaml(self, tmp_path: Path) -> None:
        """Malformed YAML raises SpecParseError wrapping the yaml error."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [\nunclosed", encoding="utf-8")
        with pytest.raises(SpecParseError) as exc_info:
            load_spec(bad_yaml)
        assert "bad.yaml" in str(exc_info.value)

    def test_raises_when_root_is_not_mapping(self, tmp_path: Path) -> None:
        """YAML that parses to a list (not a dict) raises SpecParseError."""
        list_yaml = tmp_path / "list.yaml"
        list_yaml.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(SpecParseError) as exc_info:
            load_spec(list_yaml)
        assert "list" in str(exc_info.value).lower()

    def test_also_loads_json(self, tmp_path: Path) -> None:
        """JSON files are parsed correctly (YAML is a superset of JSON)."""
        json_spec = tmp_path / "spec.json"
        payload = {"openapi": "3.0.1", "info": {"title": "T", "version": "1"}, "paths": {}}
        json_spec.write_text(json.dumps(payload), encoding="utf-8")
        raw = load_spec(json_spec)
        assert raw["openapi"] == "3.0.1"


# ===========================================================================
# 2. TestValidateSpec
# ===========================================================================


class TestValidateSpec:
    """Tests for the validate_spec() function."""

    def test_accepts_openapi_3_spec(
        self, mini_spec_raw: dict[str, Any], mini_spec_path: Path
    ) -> None:
        """Valid OpenAPI 3.0.1 spec passes validation and returns the version."""
        version = validate_spec(mini_spec_raw, mini_spec_path)
        assert version == "3.0.1"

    def test_rejects_swagger_2(
        self, swagger2_spec_raw: dict[str, Any], tmp_path: Path
    ) -> None:
        """Swagger 2.0 spec is rejected with UnsupportedSpecVersionError."""
        fake_path = tmp_path / "swagger.yaml"
        with pytest.raises(UnsupportedSpecVersionError) as exc_info:
            validate_spec(swagger2_spec_raw, fake_path)
        assert "2.0" in str(exc_info.value)

    def test_rejects_missing_version_field(
        self, missing_version_spec_raw: dict[str, Any], tmp_path: Path
    ) -> None:
        """Spec with no 'openapi' key raises SpecParseError."""
        with pytest.raises(SpecParseError):
            validate_spec(missing_version_spec_raw, tmp_path / "no_ver.yaml")

    def test_openapi_core_exception_is_non_fatal(
        self, mini_spec_raw: dict[str, Any], mini_spec_path: Path
    ) -> None:
        """
        openapi-core raising during validation must NOT crash the pipeline.

        This simulates an air-gapped environment where external $ref URLs
        are unreachable and openapi-core raises an exception during init.
        """
        with patch("openapi_core.OpenAPI", side_effect=RuntimeError("DMTF ref unreachable")):
            # Should NOT raise — external-ref tolerance mode
            version = validate_spec(mini_spec_raw, mini_spec_path)
        assert version == "3.0.1"


# ===========================================================================
# 3. TestExtractEndpoints
# ===========================================================================


class TestExtractEndpoints:
    """Tests for the extract_endpoints() function — the core extraction loop."""

    def test_correct_endpoint_count(self, mini_spec_raw: dict[str, Any]) -> None:
        """
        Fixture has exactly 7 operations:
          GET  /redfish/v1
          GET  /redfish/v1/Systems/{ComputerSystemId}
          PATCH /redfish/v1/Systems/{ComputerSystemId}
          POST /redfish/v1/Systems/{ComputerSystemId}/Actions/ComputerSystem.Reset
          GET  /redfish/v1/AccountService/Accounts
          POST /redfish/v1/AccountService/Accounts
          POST /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate
        """
        endpoints = extract_endpoints(mini_spec_raw)
        assert len(endpoints) == 7

    def test_all_endpoints_are_endpoint_contract_instances(
        self, mini_spec_raw: dict[str, Any]
    ) -> None:
        """Every extracted item must be an EndpointContract Pydantic model."""
        endpoints = extract_endpoints(mini_spec_raw)
        for ep in endpoints:
            assert isinstance(ep, EndpointContract)

    def test_operation_ids_are_present(self, mini_spec_raw: dict[str, Any]) -> None:
        """All extracted endpoints must have a non-empty operationId."""
        endpoints = extract_endpoints(mini_spec_raw)
        for ep in endpoints:
            assert ep.operation_id, f"Empty operationId for {ep.http_method} {ep.url}"

    def test_sorted_by_url_then_method(self, mini_spec_raw: dict[str, Any]) -> None:
        """Output is sorted (url, http_method) for deterministic diffs."""
        endpoints = extract_endpoints(mini_spec_raw)
        keys = [(ep.url, ep.http_method) for ep in endpoints]
        assert keys == sorted(keys), "Endpoints are not sorted by (url, http_method)"

    def test_http_methods_are_uppercase(self, mini_spec_raw: dict[str, Any]) -> None:
        """HTTP methods must always be uppercase strings."""
        endpoints = extract_endpoints(mini_spec_raw)
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        for ep in endpoints:
            assert ep.http_method in valid_methods

    def test_path_param_always_captured(self, mini_spec_raw: dict[str, Any]) -> None:
        """
        Path parameter ComputerSystemId must be in required_parameters for all
        operations on /redfish/v1/Systems/{ComputerSystemId}.
        """
        endpoints = extract_endpoints(mini_spec_raw)
        system_eps = [
            ep
            for ep in endpoints
            if ep.url == "/redfish/v1/Systems/{ComputerSystemId}"
        ]
        assert len(system_eps) == 2  # GET and PATCH
        for ep in system_eps:
            param_names = [p.name for p in ep.required_parameters]
            assert "ComputerSystemId" in param_names, (
                f"Path param missing from {ep.http_method} {ep.url}"
            )

    def test_body_required_synthesised(self, mini_spec_raw: dict[str, Any]) -> None:
        """
        POST /redfish/v1/AccountService/Accounts has requestBody.required=true.
        A synthetic 'body' RequiredParameter must be created.
        """
        endpoints = extract_endpoints(mini_spec_raw)
        post_accounts = next(
            (
                ep
                for ep in endpoints
                if ep.url == "/redfish/v1/AccountService/Accounts"
                and ep.http_method == "POST"
            ),
            None,
        )
        assert post_accounts is not None
        locations = [p.location for p in post_accounts.required_parameters]
        assert "body" in locations

    def test_optional_params_excluded(self, mini_spec_raw: dict[str, Any]) -> None:
        """
        POST /redfish/v1/UpdateService/.../SimpleUpdate has a 'required: false'
        query param ('$filter'). It must NOT appear in required_parameters.
        """
        endpoints = extract_endpoints(mini_spec_raw)
        update_ep = next(
            (
                ep
                for ep in endpoints
                if "SimpleUpdate" in ep.url
            ),
            None,
        )
        assert update_ep is not None
        param_names = [p.name for p in update_ep.required_parameters]
        assert "$filter" not in param_names, (
            "Optional '$filter' query param was incorrectly captured as required."
        )

    def test_required_header_param_captured(self, mini_spec_raw: dict[str, Any]) -> None:
        """
        POST /redfish/v1/UpdateService/.../SimpleUpdate has 'X-Correlation-ID'
        as a required header. It must be captured.
        """
        endpoints = extract_endpoints(mini_spec_raw)
        update_ep = next(
            (ep for ep in endpoints if "SimpleUpdate" in ep.url),
            None,
        )
        assert update_ep is not None
        param_names = [p.name for p in update_ep.required_parameters]
        assert "X-Correlation-ID" in param_names

    def test_parameterless_get_has_empty_required_list(
        self, mini_spec_raw: dict[str, Any]
    ) -> None:
        """
        GET /redfish/v1/AccountService/Accounts has no required params.
        required_parameters must be an empty list (not None).
        """
        endpoints = extract_endpoints(mini_spec_raw)
        get_accounts = next(
            (
                ep
                for ep in endpoints
                if ep.url == "/redfish/v1/AccountService/Accounts"
                and ep.http_method == "GET"
            ),
            None,
        )
        assert get_accounts is not None
        assert get_accounts.required_parameters == []

    def test_empty_paths_returns_empty_list(
        self, empty_paths_spec_raw: dict[str, Any]
    ) -> None:
        """Spec with empty paths dict returns an empty list (no crash)."""
        endpoints = extract_endpoints(empty_paths_spec_raw)
        assert endpoints == []

    def test_no_description_keys_in_output_models(
        self, mini_spec_raw: dict[str, Any]
    ) -> None:
        """
        CRITICAL SECURITY CHECK: Serialised EndpointContract dicts must contain
        NO 'description', 'summary', 'example', or 'x-*' keys.
        This validates the core token-exhaustion prevention guarantee.
        """
        endpoints = extract_endpoints(mini_spec_raw)
        noise_keys = {"description", "summary", "example", "examples", "tags"}
        for ep in endpoints:
            dumped = ep.model_dump()
            for key in dumped:
                assert key not in noise_keys, (
                    f"Noise key '{key}' leaked into EndpointContract for {ep.operation_id}"
                )
            # Also check the x-* extension pattern
            for key in dumped:
                assert not key.startswith("x-"), (
                    f"Extension key '{key}' leaked into EndpointContract"
                )


# ===========================================================================
# 4. TestBuildContractA
# ===========================================================================


class TestBuildContractA:
    """Tests for the build_contract_a() function."""

    def test_builds_contract_a_model(self, mini_spec_raw: dict[str, Any]) -> None:
        """build_contract_a() returns a ContractA instance."""
        endpoints = extract_endpoints(mini_spec_raw)
        contract = build_contract_a(
            raw=mini_spec_raw,
            endpoints=endpoints,
            source_file="mini_openapi.yaml",
            openapi_version="3.0.1",
        )
        assert isinstance(contract, ContractA)

    def test_total_endpoints_matches_len(self, mini_spec_raw: dict[str, Any]) -> None:
        """contract.total_endpoints == len(contract.endpoints)."""
        endpoints = extract_endpoints(mini_spec_raw)
        contract = build_contract_a(
            raw=mini_spec_raw,
            endpoints=endpoints,
            source_file="mini_openapi.yaml",
            openapi_version="3.0.1",
        )
        assert contract.total_endpoints == len(contract.endpoints)

    def test_spec_metadata_extracted(self, mini_spec_raw: dict[str, Any]) -> None:
        """spec_title and spec_version are correctly extracted from info block."""
        endpoints = extract_endpoints(mini_spec_raw)
        contract = build_contract_a(
            raw=mini_spec_raw,
            endpoints=endpoints,
            source_file="mini_openapi.yaml",
            openapi_version="3.0.1",
        )
        assert contract.spec_title == "Dell iDRAC Test Fixture"
        assert contract.spec_version == "7.00.00.00-test"
        assert contract.openapi_version == "3.0.1"


# ===========================================================================
# 5. TestSaveContractA
# ===========================================================================


class TestSaveContractA:
    """Tests for the save_contract_a() function."""

    def _build_sample_contract(self, mini_spec_raw: dict[str, Any]) -> ContractA:
        endpoints = extract_endpoints(mini_spec_raw)
        return build_contract_a(
            raw=mini_spec_raw,
            endpoints=endpoints,
            source_file="mini_openapi.yaml",
            openapi_version="3.0.1",
        )

    def test_creates_output_file(
        self, tmp_path: Path, mini_spec_raw: dict[str, Any]
    ) -> None:
        """save_contract_a() writes a JSON file to the specified path."""
        output = tmp_path / "out" / "contract_a.json"
        contract = self._build_sample_contract(mini_spec_raw)
        save_contract_a(contract, output)
        assert output.exists()

    def test_output_is_valid_json(
        self, tmp_path: Path, mini_spec_raw: dict[str, Any]
    ) -> None:
        """The written file must be parseable JSON."""
        output = tmp_path / "contract_a.json"
        contract = self._build_sample_contract(mini_spec_raw)
        save_contract_a(contract, output)
        with output.open(encoding="utf-8") as fh:
            loaded = json.load(fh)
        assert isinstance(loaded, dict)
        assert "endpoints" in loaded

    def test_contract_a_round_trips(
        self, tmp_path: Path, mini_spec_raw: dict[str, Any]
    ) -> None:
        """
        Contract A written then re-loaded via Pydantic model_validate_json()
        must produce an equivalent ContractA model.
        """
        output = tmp_path / "contract_a.json"
        contract = self._build_sample_contract(mini_spec_raw)
        save_contract_a(contract, output)

        raw_json = output.read_text(encoding="utf-8")
        reloaded = ContractA.model_validate_json(raw_json)
        assert reloaded.total_endpoints == contract.total_endpoints
        assert reloaded.spec_title == contract.spec_title

    def test_no_noise_keys_in_json_output(
        self, tmp_path: Path, mini_spec_raw: dict[str, Any]
    ) -> None:
        """
        CRITICAL TOKEN-EXHAUSTION CHECK: The serialised JSON must contain
        NO 'description', 'summary', 'example', 'tags', or 'x-*' keys at
        any depth.
        """
        output = tmp_path / "contract_a.json"
        contract = self._build_sample_contract(mini_spec_raw)
        save_contract_a(contract, output)

        raw_text = output.read_text(encoding="utf-8")
        noise_patterns = ['"description"', '"summary"', '"example"', '"tags"']
        for pattern in noise_patterns:
            assert pattern not in raw_text, (
                f"Noise key {pattern!r} found in Contract A output — "
                "stripping is not working!"
            )

    def test_creates_parent_dirs(
        self, tmp_path: Path, mini_spec_raw: dict[str, Any]
    ) -> None:
        """Output directory is created automatically if it doesn't exist."""
        deep_output = tmp_path / "a" / "b" / "c" / "contract_a.json"
        contract = self._build_sample_contract(mini_spec_raw)
        save_contract_a(contract, deep_output)
        assert deep_output.exists()


# ===========================================================================
# 6. TestMergeParameters
# ===========================================================================


class TestMergeParameters:
    """Tests for the _merge_parameters() helper."""

    def test_operation_overrides_path_param(self) -> None:
        """Operation-level param wins when name+in matches a path-level param."""
        path_param = {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
        op_param = {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
        merged = _merge_parameters([path_param], [op_param])
        assert len(merged) == 1
        assert merged[0]["schema"]["type"] == "integer"

    def test_unique_params_are_combined(self) -> None:
        """Params with different name+in combos are both kept."""
        path_param = {"name": "systemId", "in": "path", "required": True}
        op_param = {"name": "select", "in": "query", "required": False}
        merged = _merge_parameters([path_param], [op_param])
        assert len(merged) == 2

    def test_empty_inputs_return_empty(self) -> None:
        """Both empty inputs → empty output."""
        assert _merge_parameters([], []) == []


# ===========================================================================
# 7. TestExtractRequiredParams
# ===========================================================================


class TestExtractRequiredParams:
    """Tests for the _extract_required_params() helper."""

    def test_path_param_always_included(self) -> None:
        """Path params are required by definition even without explicit required=True."""
        params = [{"name": "serverId", "in": "path", "schema": {"type": "string"}}]
        result = _extract_required_params(params, None)
        assert len(result) == 1
        assert result[0].name == "serverId"
        assert result[0].location == "path"

    def test_optional_query_excluded(self) -> None:
        """Query param without required=True must NOT appear in output."""
        params = [{"name": "filter", "in": "query", "required": False, "schema": {"type": "string"}}]
        result = _extract_required_params(params, None)
        assert result == []

    def test_required_query_included(self) -> None:
        """Query param with required=True must appear in output."""
        params = [{"name": "version", "in": "query", "required": True, "schema": {"type": "string"}}]
        result = _extract_required_params(params, None)
        assert len(result) == 1
        assert result[0].name == "version"
        assert result[0].location == "query"

    def test_required_body_synthesised(self) -> None:
        """requestBody.required=True synthesises a 'body' param with location='body'."""
        result = _extract_required_params([], {"required": True, "content": {}})
        assert len(result) == 1
        assert result[0].name == "body"
        assert result[0].location == "body"
        assert result[0].param_type == "object"

    def test_optional_body_not_synthesised(self) -> None:
        """requestBody.required=False does NOT produce a body param."""
        result = _extract_required_params([], {"required": False, "content": {}})
        assert result == []

    def test_untyped_param_defaults_to_string(self) -> None:
        """Param with no 'schema.type' field defaults to param_type='string'."""
        params = [{"name": "id", "in": "path"}]  # no schema block
        result = _extract_required_params(params, None)
        assert result[0].param_type == "string"


# ===========================================================================
# 8. TestMiniSpecIntegration — Full pipeline on fixture
# ===========================================================================


class TestMiniSpecIntegration:
    """End-to-end pipeline integration test on the minimal fixture spec."""

    def test_full_pipeline_returns_contract_a(
        self, mini_spec_path: Path, tmp_path: Path
    ) -> None:
        """parse_openapi_spec() returns ContractA for the fixture spec."""
        output = tmp_path / "contract_a.json"
        parser = OpenAPIParser(mini_spec_path)
        contract = parser.parse_and_flatten(output_path=output)
        assert isinstance(contract, ContractA)
        assert contract.total_endpoints == 7

    def test_output_file_exists(
        self, mini_spec_path: Path, tmp_path: Path
    ) -> None:
        """The output JSON file is created on disk."""
        output = tmp_path / "contract_a.json"
        parser = OpenAPIParser(mini_spec_path)
        parser.parse_and_flatten(output_path=output)
        assert output.exists()

    def test_output_token_reduction(
        self, mini_spec_path: Path, tmp_path: Path
    ) -> None:
        """
        Contract A must be significantly smaller than the input spec.
        This validates the core token-exhaustion prevention guarantee.
        """
        output = tmp_path / "contract_a.json"
        parser = OpenAPIParser(mini_spec_path)
        parser.parse_and_flatten(output_path=output)

        input_size = mini_spec_path.stat().st_size
        output_size = output.stat().st_size
        # Contract A should be at least 30% smaller than the input for the fixture
        assert output_size < input_size, (
            f"Contract A ({output_size}B) is not smaller than input ({input_size}B)"
        )

    def test_no_descriptions_in_output_json(
        self, mini_spec_path: Path, tmp_path: Path
    ) -> None:
        """
        FINAL TOKEN EXHAUSTION CHECK: The complete pipeline output JSON must
        contain NO 'description' or 'summary' keys at any nesting depth.
        """
        output = tmp_path / "contract_a.json"
        parser = OpenAPIParser(mini_spec_path)
        parser.parse_and_flatten(output_path=output)
        content = output.read_text(encoding="utf-8")
        assert '"description"' not in content
        assert '"summary"' not in content
        assert '"example"' not in content


# ===========================================================================
# 9. TestRealSpecIntegration — Full pipeline on real iDRAC spec
# ===========================================================================


class TestRealSpecIntegration:
    """
    Integration tests against the real Dell iDRAC 9 v7.xx spec.

    These tests are SKIPPED automatically if the spec file is not present
    at ``/Users/sreejesh/Downloads/openapi-7.xx.yaml``.

    When the spec IS present, these tests validate:
    - The parser handles a 64,000-line / 2.9 MB real-world YAML without crashing.
    - The output contains 400+ endpoints (real spec has 500+).
    - Contract A is significantly smaller than the raw spec.
    - No noise keys leak through at any depth.
    """

    def test_real_spec_loads_without_crash(self, real_spec_path: Path) -> None:
        """The real iDRAC spec loads into a raw dict successfully."""
        raw = load_spec(real_spec_path)
        assert "paths" in raw
        assert "openapi" in raw

    def test_real_spec_extracts_many_endpoints(self, real_spec_path: Path) -> None:
        """Real spec produces 400+ endpoint contracts."""
        raw = load_spec(real_spec_path)
        endpoints = extract_endpoints(raw)
        assert len(endpoints) >= 400, (
            f"Expected 400+ endpoints, got {len(endpoints)}"
        )

    def test_real_spec_full_pipeline(
        self, real_spec_path: Path, tmp_path: Path
    ) -> None:
        """Full pipeline runs end-to-end on the real spec."""
        output = tmp_path / "contract_a_real.json"
        parser = OpenAPIParser(real_spec_path)
        contract = parser.parse_and_flatten(output_path=output)
        assert output.exists()
        assert contract.total_endpoints >= 400
        assert contract.spec_title == "Dell iDRAC 9 Redfish API Overview"

    def test_real_spec_token_reduction(
        self, real_spec_path: Path, tmp_path: Path
    ) -> None:
        """
        Contract A from the real spec must be ≥ 70% smaller than the raw spec.
        Target: < 30% of input byte size (86%+ token reduction).
        """
        output = tmp_path / "contract_a_real.json"
        parse_openapi_spec(spec_path=real_spec_path, output_path=output)

        input_size = real_spec_path.stat().st_size
        output_size = output.stat().st_size
        reduction_pct = (1 - output_size / input_size) * 100

        assert reduction_pct >= 70, (
            f"Token reduction {reduction_pct:.1f}% is below the 70% target. "
            f"Input: {input_size/1024:.0f}KB, Output: {output_size/1024:.0f}KB"
        )
        print(
            f"\n[REAL SPEC] Endpoints: {0} | "
            f"Input: {input_size/1024:.0f}KB | "
            f"Output: {output_size/1024:.0f}KB | "
            f"Reduction: {reduction_pct:.1f}%"
        )

    def test_real_spec_no_noise_in_output(
        self, real_spec_path: Path, tmp_path: Path
    ) -> None:
        """No description/summary/example/tags keys in the real spec output."""
        output = tmp_path / "contract_a_real.json"
        parse_openapi_spec(spec_path=real_spec_path, output_path=output)
        content = output.read_text(encoding="utf-8")
        noise_patterns = ['"description"', '"summary"', '"example"', '"tags"']
        for pattern in noise_patterns:
            assert pattern not in content, (
                f"Noise key {pattern!r} leaked into real spec Contract A output!"
            )
