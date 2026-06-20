"""
Dell MCP — Phase 1 Parser: Full Test Suite
==========================================
Tests for the OpenAPIParser class.
"""

from pathlib import Path
import pytest

from src.core.models import ContractA, EndpointContract
from src.parser.openapi_parser import OpenAPIParser


class TestOpenAPIParser:
    def test_loads_valid_yaml(self, mini_spec_path: Path) -> None:
        parser = OpenAPIParser(mini_spec_path)
        raw = parser.load_spec()
        assert isinstance(raw, dict)
        assert "openapi" in raw
        assert "paths" in raw

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        ghost = tmp_path / "does_not_exist.yaml"
        parser = OpenAPIParser(ghost)
        with pytest.raises(FileNotFoundError):
            parser.load_spec()

    def test_parses_endpoints_correctly(self, mini_spec_path: Path) -> None:
        parser = OpenAPIParser(mini_spec_path)
        contract = parser.parse_and_flatten()
        assert isinstance(contract, ContractA)
        assert contract.total_endpoints == 7

        endpoints = contract.endpoints
        for ep in endpoints:
            assert isinstance(ep, EndpointContract)
            assert ep.operation_id

        # Verify body parameter is synthesized
        post_accounts = next(
            (
                ep
                for ep in endpoints
                if ep.url == "/redfish/v1/AccountService/Accounts"
                and ep.method == "POST"
            ),
            None,
        )
        assert post_accounts is not None
        locations = [p.location for p in post_accounts.required_params]
        assert "body" in locations

    def test_exports_contract_a(self, mini_spec_path: Path, tmp_path: Path) -> None:
        parser = OpenAPIParser(mini_spec_path)
        output = tmp_path / "contract_a.json"
        parser.export_contract_a(output)

        assert output.exists()
        raw_json = output.read_text(encoding="utf-8")
        reloaded = ContractA.model_validate_json(raw_json)
        assert reloaded.total_endpoints == 7
