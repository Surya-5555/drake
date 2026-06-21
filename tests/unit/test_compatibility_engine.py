import pytest
import networkx as nx
from datetime import datetime, timezone
from src.core.compatibility.models import (
    DeviceFacts,
    CompatibilityDomain,
    RiskLevel,
    CompatibilityStatus,
    CapabilityInfo,
)
from src.core.compatibility.engine import (
    compare_versions,
    DependencyGraphEngine,
    CompatibilityEngine,
)


# Mock class representing step operations
class MockStep:
    def __init__(self, operation_id: str, method: str, url: str):
        self.operation_id = operation_id
        self.method = method
        self.url = url


def test_compare_versions():
    assert compare_versions("2.12.0", "2.1.2") == 1
    assert compare_versions("1.8.0", "1.10.0") == -1
    assert compare_versions("5.10.00.00", "5.10.00.00") == 0
    assert compare_versions("7.00.00.00-test", "7.00.00.00") == 0
    assert compare_versions("1.39", "1.39.0") == 0


@pytest.mark.asyncio
async def test_compatibility_engine_hardware_check(monkeypatch):
    # Setup mock repository returning active rules
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [
                {
                    "id": "rule_hw_test",
                    "rule_name": "Supported hardware",
                    "rule_type": "hardware",
                    "domain": "HARDWARE",
                    "risk_score": 10,
                    "rule_config": {
                        "supported_models": ["PowerEdge R750", "PowerEdge R650"]
                    },
                }
            ]

        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    steps = [MockStep("GET_Chassis", "GET", "/redfish/v1/Chassis/1")]

    # 1. Matching model (R750) -> Should pass
    facts_ok = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        last_scanned=datetime.now(timezone.utc),
    )
    report_ok = await engine.validate_workflow("wf_test", steps, facts_ok)
    assert report_ok.status == CompatibilityStatus.ALLOW
    assert len(report_ok.violations) == 0

    # 2. Mismatched model (R640) -> Should block
    facts_fail = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R640",
        bios_version="2.12.0",
        last_scanned=datetime.now(timezone.utc),
    )
    report_fail = await engine.validate_workflow("wf_test", steps, facts_fail)
    assert report_fail.status == CompatibilityStatus.BLOCK
    assert len(report_fail.violations) == 1
    assert report_fail.violations[0].field_checked == "device_model"


@pytest.mark.asyncio
async def test_compatibility_engine_bios_check():
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [
                {
                    "id": "rule_bios_test",
                    "rule_name": "BIOS rule",
                    "rule_type": "bios",
                    "domain": "BIOS",
                    "risk_score": 50,
                    "rule_config": {
                        "device_model": "PowerEdge R750",
                        "min_bios_version": "2.12.0",
                    },
                }
            ]

        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    steps = [MockStep("GET_Bios", "GET", "/redfish/v1/Systems/1")]

    # Older BIOS version (2.1.2 < 2.12.0) -> Should block
    facts_old = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.1.2",
        last_scanned=datetime.now(timezone.utc),
    )
    report_old = await engine.validate_workflow("wf_test", steps, facts_old)
    assert report_old.status == CompatibilityStatus.BLOCK
    assert len(report_old.violations) == 1

    # Newer BIOS version (2.15.0 >= 2.12.0) -> Should pass
    facts_new = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.15.0",
        last_scanned=datetime.now(timezone.utc),
    )
    report_new = await engine.validate_workflow("wf_test", steps, facts_new)
    assert report_new.status == CompatibilityStatus.ALLOW


@pytest.mark.asyncio
async def test_compatibility_engine_dependency_check():
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [
                {
                    "id": "rule_dep_test",
                    "rule_name": "Update depends on query",
                    "rule_type": "dependency",
                    "domain": "FIRMWARE",
                    "risk_score": 30,
                    "rule_config": {
                        "prerequisite_operation_id": "GET_Firmware",
                        "target_operation_id": "POST_Update",
                    },
                }
            ]

        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    facts = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        last_scanned=datetime.now(timezone.utc),
    )

    # 1. Target operation POST_Update is present but prerequisite GET_Firmware is missing -> Should fail
    steps_fail = [
        MockStep(
            "POST_Update",
            "POST",
            "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        )
    ]
    report_fail = await engine.validate_workflow("wf_test", steps_fail, facts)
    assert report_fail.status == CompatibilityStatus.BLOCK
    assert len(report_fail.violations) == 1

    # 2. Both operations present -> Should pass
    steps_ok = [
        MockStep("GET_Firmware", "GET", "/redfish/v1/UpdateService/FirmwareInventory"),
        MockStep(
            "POST_Update",
            "POST",
            "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        ),
    ]
    report_ok = await engine.validate_workflow("wf_test", steps_ok, facts)
    assert report_ok.status == CompatibilityStatus.ALLOW


def test_dependency_graph_engine():
    # Construct a DAG manually and verify topological sort
    G = nx.DiGraph()
    G.add_node("A", rule_name="BIOS Update")
    G.add_node("B", rule_name="LC Update")
    G.add_node("C", rule_name="RAID Update")

    # A must run before B, B before C
    G.add_edge("A", "B")
    G.add_edge("B", "C")

    engine = DependencyGraphEngine(None)
    order = engine.get_execution_order(G)
    assert order == ["A", "B", "C"]

    mermaid = engine.generate_mermaid_diagram(G)
    assert 'node_A["BIOS Update"] --> node_B["LC Update"]' in mermaid


@pytest.mark.asyncio
async def test_risk_profile_provider():
    from src.core.compatibility.repository import RiskProfileProvider
    from src.core.compatibility.models import CapabilityInfo

    class MockRiskRepo:
        async def get_profile(self, profile_id):
            return None

    provider = RiskProfileProvider(MockRiskRepo())
    profile = await provider.get_risk_profile("default_destructive")
    assert profile.base_risk_level == RiskLevel.DESTRUCTIVE
    assert profile.method_adjustments["DELETE"] == 20

    cap = CapabilityInfo(
        operation_id="test",
        capability_name="test_cap",
        compatibility_domain=CompatibilityDomain.BIOS,
        default_risk_level=RiskLevel.CONFIG_CHANGE,
        risk_profile_id="default_config_change",
    )
    profile_cap = await provider.get_risk_profile_for_capability(cap)
    assert profile_cap.id == "default_config_change"


@pytest.mark.asyncio
async def test_capability_discovery_service():
    from src.core.compatibility.engine import CapabilityDiscoveryService

    class MockRepo:
        def __init__(self):
            self.session_factory = None

        async def get_capability_by_operation(self, op_id):
            return None

    service = CapabilityDiscoveryService(MockRepo())

    async def mock_save(cap_info):
        pass

    service.save_candidate_capability = mock_save

    endpoints = [
        {
            "operation_id": "POST_SimpleUpdate",
            "method": "POST",
            "url": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            "request_schema": {},
        }
    ]

    discovered = await service.discover_capabilities(endpoints)
    assert len(discovered) == 1
    assert discovered[0].compatibility_domain == CompatibilityDomain.FIRMWARE
    assert discovered[0].default_risk_level == RiskLevel.DESTRUCTIVE


@pytest.mark.asyncio
async def test_blast_radius_engine():
    from src.core.compatibility.engine import BlastRadiusEngine

    class MockRepo:
        async def get_dependencies(self):
            return []

    engine = BlastRadiusEngine(MockRepo())

    radius, reason = await engine.calculate_blast_radius([], {"GOVERNANCE"})
    assert radius == "CLUSTER"

    radius, reason = await engine.calculate_blast_radius([], {"HARDWARE"})
    assert radius == "NODE"


# ===========================================================================
# Expanded Test Cases for Coverage Hardening
# ===========================================================================


@pytest.mark.asyncio
async def test_compatibility_engine_hardware_check_missing_model():
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [
                {
                    "id": "rule_hw_test",
                    "rule_name": "Supported hardware",
                    "rule_type": "hardware",
                    "domain": "HARDWARE",
                    "risk_score": 10,
                    "rule_config": {"supported_models": ["PowerEdge R750"]},
                }
            ]

        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    steps = [MockStep("GET_Chassis", "GET", "/redfish/v1/Chassis/1")]

    # Device model not populated (empty or missing) -> should block
    facts_missing = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="",
        bios_version="2.12.0",
        last_scanned=datetime.now(timezone.utc),
    )
    report = await engine.validate_workflow("wf_test", steps, facts_missing)
    assert report.status == CompatibilityStatus.BLOCK
    assert len(report.violations) == 1
    assert report.violations[0].field_checked == "device_model"


@pytest.mark.asyncio
async def test_compatibility_engine_bios_invalid_format():
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [
                {
                    "id": "rule_bios_test",
                    "rule_name": "BIOS rule",
                    "rule_type": "bios",
                    "domain": "BIOS",
                    "risk_score": 50,
                    "rule_config": {
                        "device_model": "PowerEdge R750",
                        "min_bios_version": "2.12.0",
                    },
                }
            ]

        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    steps = [MockStep("GET_Bios", "GET", "/redfish/v1/Systems/1")]

    # Malformed BIOS version -> should block
    facts_malformed = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="invalid-version-text",
        last_scanned=datetime.now(timezone.utc),
    )
    report = await engine.validate_workflow("wf_test", steps, facts_malformed)
    assert report.status == CompatibilityStatus.BLOCK
    assert len(report.violations) == 1


@pytest.mark.asyncio
async def test_compatibility_engine_bios_missing_version():
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [
                {
                    "id": "rule_bios_test",
                    "rule_name": "BIOS rule",
                    "rule_type": "bios",
                    "domain": "BIOS",
                    "risk_score": 50,
                    "rule_config": {
                        "device_model": "PowerEdge R750",
                        "min_bios_version": "2.12.0",
                    },
                }
            ]

        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    steps = [MockStep("GET_Bios", "GET", "/redfish/v1/Systems/1")]

    # Missing BIOS version -> should block
    facts_missing = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="",
        last_scanned=datetime.now(timezone.utc),
    )
    report = await engine.validate_workflow("wf_test", steps, facts_missing)
    assert report.status == CompatibilityStatus.BLOCK


@pytest.mark.asyncio
async def test_compatibility_engine_firmware_check():
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [
                {
                    "id": "rule_fw_test",
                    "rule_name": "Firmware range rule",
                    "rule_type": "firmware",
                    "domain": "FIRMWARE",
                    "risk_score": 40,
                    "rule_config": {
                        "target_component": "iDRAC9",
                        "min_version": "5.10.00.00",
                    },
                }
            ]

        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    steps = [MockStep("POST_Update", "POST", "/redfish/v1/UpdateService")]

    # 1. Component missing from facts -> should pass (the engine only checks version if component is present)
    facts_missing = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        firmware_inventory={},
        last_scanned=datetime.now(timezone.utc),
    )
    report1 = await engine.validate_workflow("wf_test", steps, facts_missing)
    assert report1.status == CompatibilityStatus.ALLOW
    assert len(report1.violations) == 0

    # 2. Version below minimum -> should block
    facts_below = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        firmware_inventory={"iDRAC9": "4.40.40.40"},
        last_scanned=datetime.now(timezone.utc),
    )
    report2 = await engine.validate_workflow("wf_test", steps, facts_below)
    assert report2.status == CompatibilityStatus.BLOCK
    assert len(report2.violations) == 1
    assert "iDRAC9" in report2.violations[0].remediation_step

    # 3. Version in range -> should pass
    facts_ok = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        firmware_inventory={"iDRAC9": "5.20.20.20"},
        last_scanned=datetime.now(timezone.utc),
    )
    report4 = await engine.validate_workflow("wf_test", steps, facts_ok)
    assert report4.status == CompatibilityStatus.ALLOW


@pytest.mark.asyncio
async def test_compatibility_engine_scoring_and_verdicts():
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            # Return rules that fail depending on hardware and BIOS
            if domain == "HARDWARE":
                return [
                    {
                        "id": "rule_hw",
                        "rule_name": "HW supported",
                        "rule_type": "hardware",
                        "domain": "HARDWARE",
                        "risk_score": 10,
                        "rule_config": {"supported_models": ["PowerEdge R750"]},
                    }
                ]
            elif domain == "BIOS":
                return [
                    {
                        "id": "rule_bios",
                        "rule_name": "BIOS check",
                        "rule_type": "bios",
                        "domain": "BIOS",
                        "risk_score": 30,
                        "rule_config": {
                            "device_model": "PowerEdge R640",
                            "min_bios_version": "2.12.0",
                        },
                    }
                ]
            return []

        async def get_capability_by_operation(self, op_id) -> CapabilityInfo:
            from src.core.compatibility.models import CapabilityInfo

            domain = (
                CompatibilityDomain.BIOS
                if "Bios" in op_id
                else CompatibilityDomain.HARDWARE
            )
            return CapabilityInfo(
                operation_id=op_id,
                capability_name="delete_system"
                if "delete" in op_id.lower()
                else "get_bios",
                compatibility_domain=domain,
                default_risk_level=RiskLevel.DESTRUCTIVE,
                risk_profile_id="default_destructive",
            )

    engine = CompatibilityEngine(MockRepo())
    steps = [
        MockStep("DELETE_System", "DELETE", "/redfish/v1/Systems/1"),
        MockStep("GET_Bios", "GET", "/redfish/v1/Systems/1/Bios"),
    ]

    # Multiple failures (HW mismatches and BIOS mismatches)
    # R640 fails HW rule (supported=R750), and BIOS version (2.1.2 < 2.12.0)
    facts = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R640",
        bios_version="2.1.2",
        last_scanned=datetime.now(timezone.utc),
    )

    report = await engine.validate_workflow("wf_test", steps, facts)
    assert report.status == CompatibilityStatus.BLOCK
    assert len(report.violations) == 2
    # Verify score is reduced appropriately
    assert report.compatibility_score < 100
    assert report.risk_score > 0


def test_dependency_graph_engine_dag_traversals():
    # Empty Graph Sort
    engine = DependencyGraphEngine(None)
    G_empty = nx.DiGraph()
    assert engine.get_execution_order(G_empty) == []

    # Single Node Sort
    G_single = nx.DiGraph()
    G_single.add_node("A", rule_name="Step A")
    assert engine.get_execution_order(G_single) == ["A"]

    # Circular Dependency returns nodes list
    G_cycle = nx.DiGraph()
    G_cycle.add_node("A", rule_name="A")
    G_cycle.add_node("B", rule_name="B")
    G_cycle.add_edge("A", "B")
    G_cycle.add_edge("B", "A")

    order_cycle = engine.get_execution_order(G_cycle)
    assert set(order_cycle) == {"A", "B"}


@pytest.mark.asyncio
async def test_blast_radius_engine_escalation():
    from src.core.compatibility.engine import BlastRadiusEngine

    class MockRepo:
        async def get_dependencies(self):
            return [("A", "B")]

    engine = BlastRadiusEngine(MockRepo())

    # 1. Test standard node impact
    radius, _ = await engine.calculate_blast_radius([], {CompatibilityDomain.TELEMETRY})
    assert radius == "NODE"

    # 2. Test power configurations affect the chassis
    radius, _ = await engine.calculate_blast_radius([], {CompatibilityDomain.POWER})
    assert radius == "CHASSIS"

    # 3. Test storage controller firmware updates escalate to rack/chassis
    radius, _ = await engine.calculate_blast_radius([], {CompatibilityDomain.STORAGE})
    assert radius in ("CHASSIS", "RACK")


@pytest.mark.asyncio
async def test_explainability_graph_generation():
    from src.core.compatibility.engine import DependencyGraphEngine
    from src.core.compatibility.models import GovernanceExplainabilityReport

    # Mock Dependency Graph
    G = nx.DiGraph()
    G.add_node("step_1", rule_name="GET Chassis")
    G.add_node("step_2", rule_name="POST Configuration")
    G.add_edge("step_1", "step_2")

    engine = DependencyGraphEngine(None)
    mermaid = engine.generate_mermaid_diagram(G)
    assert "node_step_1" in mermaid
    assert "node_step_2" in mermaid

    # Validate BaseExplainabilityReport validation
    report = GovernanceExplainabilityReport(
        workflow_id="wf_test",
        workflow_display_name="Test Workflow",
        compatibility_score=80,
        overall_risk_level="high",
        confidence_level=90,
        blast_radius="NODE",
        dependency_graph_mermaid=mermaid,
        remediation_actions=["Update BIOS to 2.12.0"],
    )
    assert report.workflow_id == "wf_test"
    assert "node_step_1" in report.dependency_graph_mermaid


@pytest.mark.asyncio
async def test_capability_discovery_service_branches():
    from src.core.compatibility.engine import CapabilityDiscoveryService

    # Mock repository returning existing override or None
    class MockRepo:
        def __init__(self, override_cap=None):
            self.override_cap = override_cap

        async def get_capability_by_operation(self, op_id):
            return self.override_cap

        async def save_candidate_capability(self, cap_info):
            pass

    # Test override path
    from src.core.compatibility.models import CapabilityInfo

    override_cap = CapabilityInfo(
        operation_id="op_override",
        capability_name="OVERRIDE",
        compatibility_domain=CompatibilityDomain.GOVERNANCE,
        default_risk_level=RiskLevel.DESTRUCTIVE,
        is_manual_override=1,
        risk_profile_id="default_destructive",
    )
    service_override = CapabilityDiscoveryService(MockRepo(override_cap))
    res_override = await service_override.discover_capabilities(
        [
            {
                "operation_id": "op_override",
                "method": "POST",
                "url": "/redfish/v1/Systems",
            }
        ]
    )
    assert len(res_override) == 1
    assert res_override[0].capability_name == "OVERRIDE"

    # Test all branches in mapping URLs/methods
    service_normal = CapabilityDiscoveryService(MockRepo(None))

    # We monkeypatch save_candidate_capability to do nothing
    async def dummy_save(cap_info):
        pass

    service_normal.save_candidate_capability = dummy_save

    test_cases = [
        # 1. UpdateService.SimpleUpdate
        {
            "operation_id": "SimpleUpdate",
            "method": "POST",
            "url": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            "expected_domain": CompatibilityDomain.FIRMWARE,
            "expected_risk": RiskLevel.DESTRUCTIVE,
            "expected_name": "FIRMWARE_UPDATE",
        },
        # 2. SoftwareInventory / FirmwareInventory
        {
            "operation_id": "GetFW",
            "method": "GET",
            "url": "/redfish/v1/UpdateService/FirmwareInventory",
            "expected_domain": CompatibilityDomain.FIRMWARE,
            "expected_risk": RiskLevel.READ_ONLY,
            "expected_name": "FIRMWARE_QUERY",
        },
        # 3. Systems Reset
        {
            "operation_id": "ResetSystem",
            "method": "POST",
            "url": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
            "expected_domain": CompatibilityDomain.POWER,
            "expected_risk": RiskLevel.DESTRUCTIVE,
            "expected_name": "POWER_CONTROL",
        },
        # 4. Systems Config PATCH
        {
            "operation_id": "PatchBios",
            "method": "PATCH",
            "url": "/redfish/v1/Systems/1",
            "expected_domain": CompatibilityDomain.BIOS,
            "expected_risk": RiskLevel.CONFIG_CHANGE,
            "expected_name": "BIOS_UPDATE",
        },
        # 5. Systems Read
        {
            "operation_id": "GetSystem",
            "method": "GET",
            "url": "/redfish/v1/Systems/1",
            "expected_domain": CompatibilityDomain.BIOS,
            "expected_risk": RiskLevel.READ_ONLY,
            "expected_name": "BIOS_QUERY",
        },
        # 6. Chassis Power
        {
            "operation_id": "GetPower",
            "method": "GET",
            "url": "/redfish/v1/Chassis/1/Power",
            "expected_domain": CompatibilityDomain.POWER,
            "expected_risk": RiskLevel.READ_ONLY,
            "expected_name": "POWER_QUERY",
        },
        # 7. Chassis Generic
        {
            "operation_id": "GetChassis",
            "method": "GET",
            "url": "/redfish/v1/Chassis/1",
            "expected_domain": CompatibilityDomain.HARDWARE,
            "expected_risk": RiskLevel.READ_ONLY,
            "expected_name": "CHASSIS_QUERY",
        },
        # 8. Storage control
        {
            "operation_id": "PostStorage",
            "method": "POST",
            "url": "/redfish/v1/Storage",
            "expected_domain": CompatibilityDomain.STORAGE,
            "expected_risk": RiskLevel.CONFIG_CHANGE,
            "expected_name": "STORAGE_CONTROL",
        },
        # 9. Storage read
        {
            "operation_id": "GetStorage",
            "method": "GET",
            "url": "/redfish/v1/Storage",
            "expected_domain": CompatibilityDomain.STORAGE,
            "expected_risk": RiskLevel.READ_ONLY,
            "expected_name": "STORAGE_QUERY",
        },
        # 10. GET general
        {
            "operation_id": "GenericGet",
            "method": "GET",
            "url": "/redfish/v1/Managers",
            "expected_domain": CompatibilityDomain.HARDWARE,
            "expected_risk": RiskLevel.READ_ONLY,
            "expected_name": "GENERIC_QUERY",
        },
        # 11. POST general
        {
            "operation_id": "GenericPost",
            "method": "POST",
            "url": "/redfish/v1/Managers",
            "expected_domain": CompatibilityDomain.GOVERNANCE,
            "expected_risk": RiskLevel.CONFIG_CHANGE,
            "expected_name": "GENERIC_CHANGE",
        },
    ]

    for tc in test_cases:
        res = await service_normal.discover_capabilities(
            [
                {
                    "operation_id": tc["operation_id"],
                    "method": tc["method"],
                    "url": tc["url"],
                }
            ]
        )
        assert len(res) == 1
        assert res[0].compatibility_domain == tc["expected_domain"]
        assert res[0].default_risk_level == tc["expected_risk"]
        assert res[0].capability_name == tc["expected_name"]


@pytest.mark.asyncio
async def test_capability_discovery_service_save_candidate():
    from src.core.compatibility.engine import CapabilityDiscoveryService
    from src.core.compatibility.models import CapabilityInfo
    from unittest.mock import AsyncMock, MagicMock

    # Setup database mocks
    mock_db_cap = MagicMock()
    mock_db_cap.is_manual_override = 0

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [
        None,
        mock_db_cap,
    ]  # first call is missing, second call is found

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    class MockRepo:
        def __init__(self):
            # context manager factory
            self.session_factory = MagicMock()
            self.session_factory.return_value.__aenter__.return_value = mock_session

    service = CapabilityDiscoveryService(MockRepo())
    cap_info = CapabilityInfo(
        operation_id="op_test",
        capability_name="FIRMWARE_QUERY",
        compatibility_domain=CompatibilityDomain.FIRMWARE,
        default_risk_level=RiskLevel.READ_ONLY,
        risk_profile_id="default_read_only",
        is_manual_override=0,
        discovery_confidence=1.0,
    )

    # 1. Test insert path (db_cap is None)
    await service.save_candidate_capability(cap_info)
    assert mock_session.add.called
    assert mock_session.commit.called

    # 2. Test update path (db_cap exists and is_manual_override == 0)
    mock_session.add.reset_mock()
    await service.save_candidate_capability(cap_info)
    assert not mock_session.add.called
    assert mock_db_cap.capability_name == "FIRMWARE_QUERY"


@pytest.mark.asyncio
async def test_blast_radius_cross_links():
    from src.core.compatibility.engine import BlastRadiusEngine

    # MockRepo with get_dependencies returning > 5 edges
    class MockRepo:
        async def get_dependencies(self):
            return [
                ("1", "2"),
                ("3", "4"),
                ("5", "6"),
                ("7", "8"),
                ("9", "10"),
                ("11", "12"),
            ]

    engine = BlastRadiusEngine(MockRepo())
    radius, reason = await engine.calculate_blast_radius(
        [], {CompatibilityDomain.POWER.value}
    )
    assert radius == "RACK"
    assert "cross-node dependencies" in reason


@pytest.mark.asyncio
async def test_dependency_graph_build_dag():
    from src.core.compatibility.engine import DependencyGraphEngine

    class MockRepo:
        async def get_active_rules(self):
            return [
                {"id": "rule1", "rule_name": "Rule 1", "rule_type": "hardware"},
                {"id": "rule2", "rule_name": "Rule 2", "rule_type": "bios"},
            ]

        async def get_dependencies(self):
            return [("rule2", "rule1")]

    engine = DependencyGraphEngine(MockRepo())
    dag = await engine.build_dependencies_dag()
    assert dag.has_node("rule1")
    assert dag.has_node("rule2")
    assert dag.has_edge(
        "rule1", "rule2"
    )  # prereq -> rule_id (rule1 is prereq, rule2 is rule_id)


def test_dependency_graph_mermaid_degree_zero():
    from src.core.compatibility.engine import DependencyGraphEngine
    import networkx as nx

    engine = DependencyGraphEngine(None)
    G = nx.DiGraph()
    G.add_node("rule1", rule_name="Rule 1")

    mermaid = engine.generate_mermaid_diagram(G)
    assert 'node_rule1["Rule 1"]' in mermaid


def test_dependency_graph_build_operations_dag():
    from src.core.compatibility.engine import DependencyGraphEngine

    engine = DependencyGraphEngine(None)
    active_rules = [
        {
            "rule_type": "dependency",
            "rule_config": {
                "prerequisite_operation_id": "op_pre",
                "target_operation_id": "op_target",
            },
        },
        {"rule_type": "hardware", "rule_config": {}},
    ]
    g = engine.build_operations_dag(active_rules)
    assert g.has_node("op_pre")
    assert g.has_node("op_target")
    assert g.has_edge("op_pre", "op_target")


def test_dependency_graph_verify_execution_order():
    from src.core.compatibility.engine import DependencyGraphEngine
    import networkx as nx

    engine = DependencyGraphEngine(None)
    G = nx.DiGraph()
    G.add_edge("op_pre", "op_target")

    # Correct execution order
    violations = engine.verify_execution_order(
        G, [MockStep("op_pre", "GET", "/url"), MockStep("op_target", "POST", "/url")]
    )
    assert len(violations) == 0

    # Missing prerequisite
    violations_missing = engine.verify_execution_order(
        G, [MockStep("op_target", "POST", "/url")]
    )
    assert len(violations_missing) == 1
    assert violations_missing[0] == ("op_pre", "op_target")

    # Invalid ordering (pre after target)
    violations_order = engine.verify_execution_order(
        G, [MockStep("op_target", "POST", "/url"), MockStep("op_pre", "GET", "/url")]
    )
    assert len(violations_order) == 1


@pytest.mark.asyncio
async def test_compatibility_engine_dependency_ordering_and_safety():
    from src.core.compatibility.engine import CompatibilityEngine
    from src.core.compatibility.models import DeviceFacts, CompatibilityStatus
    from datetime import datetime, timezone

    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [
                # 1. Dependency ordering rule
                {
                    "id": "rule_dep",
                    "rule_name": "Ordering rule",
                    "rule_type": "dependency",
                    "domain": "FIRMWARE",
                    "rule_config": {
                        "prerequisite_operation_id": "op_pre",
                        "target_operation_id": "op_target",
                    },
                },
                # 2. Safety combination rule
                {
                    "id": "rule_safety",
                    "rule_name": "Safety rule",
                    "rule_type": "safety",
                    "domain": "FIRMWARE",
                    "rule_config": {
                        "forbidden_combinations": ["op_forbidden_1", "op_forbidden_2"]
                    },
                },
            ]

        async def get_capability_by_operation(self, op_id):
            from src.core.compatibility.models import CapabilityInfo

            return CapabilityInfo(
                operation_id=op_id,
                capability_name=op_id,
                compatibility_domain=CompatibilityDomain.FIRMWARE,
                default_risk_level=RiskLevel.READ_ONLY,
                risk_profile_id="default_read_only",
            )

    engine = CompatibilityEngine(MockRepo())
    facts = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        last_scanned=datetime.now(timezone.utc),
    )

    # Test dependency ordering violation (pre after target)
    steps_order_fail = [
        MockStep("op_target", "POST", "/url"),
        MockStep("op_pre", "GET", "/url"),
    ]
    report_order = await engine.validate_workflow("wf_test", steps_order_fail, facts)
    assert report_order.status == CompatibilityStatus.BLOCK
    assert any(
        "Prerequisite operation is executed after" in v.actual_value
        for v in report_order.violations
    )

    # Test safety combination violation
    steps_safety_fail = [
        MockStep("op_forbidden_1", "POST", "/url"),
        MockStep("op_forbidden_2", "POST", "/url"),
    ]
    report_safety = await engine.validate_workflow("wf_test", steps_safety_fail, facts)
    assert report_safety.status == CompatibilityStatus.BLOCK
    assert any(
        "Conflict combination sequence" in v.actual_value
        for v in report_safety.violations
    )


@pytest.mark.asyncio
async def test_compatibility_engine_confidence_cache_staleness():
    from src.core.compatibility.engine import CompatibilityEngine
    from src.core.compatibility.models import DeviceFacts
    from datetime import datetime, timedelta, timezone

    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return []

        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    steps = [MockStep("GET_Chassis", "GET", "/url")]

    # 1. Cached facts within TTL (age <= 300s)
    facts_fresh = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        is_live=False,
        last_scanned=datetime.now(timezone.utc) - timedelta(seconds=150),
    )
    report_fresh = await engine.validate_workflow("wf_test", steps, facts_fresh)
    assert report_fresh.confidence_score == 80

    # 2. Cached facts stale (age > 300s)
    facts_stale = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        is_live=False,
        last_scanned=datetime.utcnow() - timedelta(seconds=400),
    )
    report_stale = await engine.validate_workflow("wf_test", steps, facts_stale)
    assert report_stale.confidence_score == 40
    assert any("Stale Device Inventory Cache" in f.title for f in report_stale.findings)
