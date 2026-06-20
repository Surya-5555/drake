import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from src.core.compatibility.models import (
    CapabilityInfo,
    CompatibilityDomain,
    RiskLevel,
    CompatibilityReport,
    CompatibilityStatus,
    DeviceFacts,
)
from src.core.compatibility.repository import (
    CompatibilityRepository,
    RiskProfileRepository,
    RiskProfileProvider,
)


@pytest.mark.asyncio
async def test_capabilities_registry_and_by_operation():
    # Setup mock database entities
    mock_db_cap = MagicMock()
    mock_db_cap.operation_id = "op_test"
    mock_db_cap.capability_name = "test_cap"
    mock_db_cap.compatibility_domain = "BIOS"
    mock_db_cap.default_risk_level = "READ_ONLY"
    mock_db_cap.parameters_schema = '{"param": "type"}'

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_db_cap]
    mock_result.scalar_one_or_none.return_value = mock_db_cap

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = mock_session

    repo = CompatibilityRepository(session_factory)

    # Test get_capabilities_registry
    registry = await repo.get_capabilities_registry()
    assert "op_test" in registry
    assert registry["op_test"].capability_name == "test_cap"
    assert registry["op_test"].compatibility_domain == CompatibilityDomain.BIOS
    assert registry["op_test"].default_risk_level == RiskLevel.READ_ONLY
    assert registry["op_test"].parameters_schema == {"param": "type"}

    # Test get_capability_by_operation success
    cap = await repo.get_capability_by_operation("op_test")
    assert cap is not None
    assert cap.operation_id == "op_test"

    # Test get_capability_by_operation miss
    mock_result.scalar_one_or_none.return_value = None
    cap_miss = await repo.get_capability_by_operation("op_absent")
    assert cap_miss is None


@pytest.mark.asyncio
async def test_active_rules_and_rules_for_domain():
    mock_rule = MagicMock()
    mock_rule.id = "rule1"
    mock_rule.rule_name = "Rule One"
    mock_rule.rule_type = "hardware"
    mock_rule.domain = "HARDWARE"
    mock_rule.rule_version = 1
    mock_rule.effective_from = "2026-06-01T00:00:00"
    mock_rule.effective_to = None
    mock_rule.created_by = "admin"
    mock_rule.superseded_by = None
    mock_rule.change_reason = "Initial"
    mock_rule.rule_config = '{"supported_models": ["R750"]}'

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_rule]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = mock_session

    repo = CompatibilityRepository(session_factory)

    # 1. Test active rules with naive datetime
    rules_naive = await repo.get_active_rules(as_of=datetime.now())
    assert len(rules_naive) == 1
    assert rules_naive[0]["id"] == "rule1"
    assert rules_naive[0]["rule_config"] == {"supported_models": ["R750"]}

    # 2. Test active rules with timezone-aware datetime
    rules_aware = await repo.get_active_rules(as_of=datetime.now(timezone.utc))
    assert len(rules_aware) == 1

    # 3. Test rules filtered by domain
    rules_domain = await repo.get_rules_for_domain("HARDWARE", as_of=datetime.now())
    assert len(rules_domain) == 1
    assert rules_domain[0]["domain"] == "HARDWARE"


@pytest.mark.asyncio
async def test_get_dependencies():
    mock_dep = MagicMock()
    mock_dep.rule_id = "rule_b"
    mock_dep.prerequisite_rule_id = "rule_a"

    # DBDependency select returns row mappings
    mock_result = MagicMock()
    mock_result.all.return_value = [(mock_dep,)]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = mock_session

    repo = CompatibilityRepository(session_factory)
    deps = await repo.get_dependencies()
    assert deps == [("rule_b", "rule_a")]


@pytest.mark.asyncio
async def test_save_report_and_get_reports():
    mock_session = AsyncMock()
    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = mock_session

    repo = CompatibilityRepository(session_factory)

    report = CompatibilityReport(
        id="rep_123",
        workflow_id="wf_123",
        target_ip="192.168.0.120",
        status=CompatibilityStatus.ALLOW,
        compatibility_score=95,
        risk_score=20,
        blast_radius="NODE",
        confidence_score=90,
        timestamp=datetime.now(timezone.utc),
    )

    # Test save_report
    await repo.save_report(report)
    assert mock_session.add.called
    assert mock_session.commit.called

    # Test get_reports_for_workflow success
    mock_db_report = MagicMock()
    mock_db_report.report_json = report.model_dump_json()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_db_report]
    mock_session.execute.return_value = mock_result

    reports = await repo.get_reports_for_workflow("wf_123")
    assert len(reports) == 1
    assert reports[0].id == "rep_123"

    # Test get_reports_for_workflow with malformed JSON
    mock_db_report_bad = MagicMock()
    mock_db_report_bad.report_json = "{bad-json}"
    mock_result.scalars.return_value.all.return_value = [mock_db_report_bad]
    reports_bad = await repo.get_reports_for_workflow("wf_123")
    assert len(reports_bad) == 0


@pytest.mark.asyncio
async def test_save_device_facts_insert_and_update():
    mock_session = AsyncMock()
    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = mock_session

    repo = CompatibilityRepository(session_factory)

    facts = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        lifecycle_controller_version="5.10.00.00",
        firmware_inventory={"iDRAC9": "5.10.00.00"},
        last_scanned=datetime.now(timezone.utc),
    )

    # 1. Test insert path (device cache is missing)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    await repo.save_device_facts(facts)
    assert mock_session.add.called
    assert mock_session.commit.called

    # 2. Test update path (device cache exists)
    mock_device = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_device
    mock_session.add.reset_mock()

    await repo.save_device_facts(facts)
    assert not mock_session.add.called
    assert mock_device.device_model == "PowerEdge R750"
    assert mock_device.bios_version == "2.12.0"
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_supersede_rule():
    mock_session = AsyncMock()
    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = mock_session

    repo = CompatibilityRepository(session_factory)

    mock_old_rule = MagicMock()
    mock_old_rule.id = "rule_old"
    mock_old_rule.rule_version = 2
    mock_old_rule.effective_to = None
    mock_old_rule.superseded_by = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_old_rule
    mock_session.execute.return_value = mock_result

    new_rule_data = {
        "id": "rule_new_123",
        "rule_name": "New Rule",
        "rule_type": "bios",
        "domain": "BIOS",
        "rule_config": {"device_model": "R750", "min_bios_version": "2.15.0"},
    }

    # Test superseding rule
    new_rule_id = await repo.supersede_rule("rule_old", new_rule_data)
    assert new_rule_id == "rule_new_123"
    assert mock_old_rule.effective_to is not None
    assert mock_old_rule.superseded_by == "rule_new_123"
    assert mock_session.add.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_risk_profile_repository():
    mock_db_profile = MagicMock()
    mock_db_profile.id = "profile_1"
    mock_db_profile.profile_name = "Profile One"
    mock_db_profile.base_risk_level = "CONFIG_CHANGE"
    mock_db_profile.method_adjustments = '{"POST": 10}'
    mock_db_profile.order_coefficient = 1.5
    mock_db_profile.max_risk_score = 90

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_db_profile]
    mock_result.scalar_one_or_none.return_value = mock_db_profile

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = mock_session

    repo = RiskProfileRepository(session_factory)

    # 1. Test get_all_profiles
    profiles = await repo.get_all_profiles()
    assert len(profiles) == 1
    assert profiles[0].id == "profile_1"
    assert profiles[0].base_risk_level == RiskLevel.CONFIG_CHANGE
    assert profiles[0].method_adjustments == {"POST": 10}

    # 2. Test get_profile success
    profile = await repo.get_profile("profile_1")
    assert profile is not None
    assert profile.max_risk_score == 90

    # 3. Test get_profile miss
    mock_result.scalar_one_or_none.return_value = None
    profile_miss = await repo.get_profile("profile_absent")
    assert profile_miss is None


@pytest.mark.asyncio
async def test_risk_profile_provider_fallback_and_cache():
    # Repository returns None to trigger fallbacks
    mock_repo = AsyncMock()
    mock_repo.get_profile.return_value = None

    provider = RiskProfileProvider(mock_repo)

    # 1. Fetch destructive fallback
    profile1 = await provider.get_risk_profile("default_destructive")
    assert profile1.base_risk_level == RiskLevel.DESTRUCTIVE
    assert profile1.max_risk_score == 100

    # 2. Subsequent call should hit cache (verify repository isn't called again)
    mock_repo.get_profile.reset_mock()
    profile2 = await provider.get_risk_profile("default_destructive")
    assert profile2 is profile1
    assert not mock_repo.get_profile.called

    # 3. Fetch unknown fallback (returns read-only)
    profile_unknown = await provider.get_risk_profile("some_unknown_profile_id")
    assert profile_unknown.base_risk_level == RiskLevel.READ_ONLY

    # 4. Get profile for capability
    capability = CapabilityInfo(
        operation_id="op_1",
        capability_name="cap_1",
        compatibility_domain=CompatibilityDomain.GOVERNANCE,
        default_risk_level=RiskLevel.DESTRUCTIVE,
        risk_profile_id="default_destructive",
    )
    profile_cap = await provider.get_risk_profile_for_capability(capability)
    assert profile_cap.id == "default_destructive"
