import pytest
import networkx as nx
from datetime import datetime, timezone
from src.core.compatibility.models import (
    DeviceFacts,
    CompatibilityDomain,
    RiskLevel,
    CompatibilityStatus
)
from src.core.compatibility.engine import compare_versions, DependencyGraphEngine, CompatibilityEngine
from src.core.compatibility.repository import CompatibilityRepository

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
            return [{
                "id": "rule_hw_test",
                "rule_name": "Supported hardware",
                "rule_type": "hardware",
                "domain": "HARDWARE",
                "risk_score": 10,
                "rule_config": {"supported_models": ["PowerEdge R750", "PowerEdge R650"]}
            }]
        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    steps = [MockStep("GET_Chassis", "GET", "/redfish/v1/Chassis/1")]

    # 1. Matching model (R750) -> Should pass
    facts_ok = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        last_scanned=datetime.now(timezone.utc)
    )
    report_ok = await engine.validate_workflow("wf_test", steps, facts_ok)
    assert report_ok.status == CompatibilityStatus.ALLOW
    assert len(report_ok.violations) == 0

    # 2. Mismatched model (R640) -> Should block
    facts_fail = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R640",
        bios_version="2.12.0",
        last_scanned=datetime.now(timezone.utc)
    )
    report_fail = await engine.validate_workflow("wf_test", steps, facts_fail)
    assert report_fail.status == CompatibilityStatus.BLOCK
    assert len(report_fail.violations) == 1
    assert report_fail.violations[0].field_checked == "device_model"


@pytest.mark.asyncio
async def test_compatibility_engine_bios_check():
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [{
                "id": "rule_bios_test",
                "rule_name": "BIOS rule",
                "rule_type": "bios",
                "domain": "BIOS",
                "risk_score": 50,
                "rule_config": {"device_model": "PowerEdge R750", "min_bios_version": "2.12.0"}
            }]
        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    steps = [MockStep("GET_Bios", "GET", "/redfish/v1/Systems/1")]

    # Older BIOS version (2.1.2 < 2.12.0) -> Should block
    facts_old = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.1.2",
        last_scanned=datetime.now(timezone.utc)
    )
    report_old = await engine.validate_workflow("wf_test", steps, facts_old)
    assert report_old.status == CompatibilityStatus.BLOCK
    assert len(report_old.violations) == 1

    # Newer BIOS version (2.15.0 >= 2.12.0) -> Should pass
    facts_new = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.15.0",
        last_scanned=datetime.now(timezone.utc)
    )
    report_new = await engine.validate_workflow("wf_test", steps, facts_new)
    assert report_new.status == CompatibilityStatus.ALLOW


@pytest.mark.asyncio
async def test_compatibility_engine_dependency_check():
    class MockRepo:
        async def get_rules_for_domain(self, domain, as_of=None):
            return [{
                "id": "rule_dep_test",
                "rule_name": "Update depends on query",
                "rule_type": "dependency",
                "domain": "FIRMWARE",
                "risk_score": 30,
                "rule_config": {
                    "prerequisite_operation_id": "GET_Firmware",
                    "target_operation_id": "POST_Update"
                }
            }]
        async def get_capability_by_operation(self, op_id):
            return None

    engine = CompatibilityEngine(MockRepo())
    facts = DeviceFacts(
        target_ip="192.168.0.120",
        device_model="PowerEdge R750",
        bios_version="2.12.0",
        last_scanned=datetime.now(timezone.utc)
    )

    # 1. Target operation POST_Update is present but prerequisite GET_Firmware is missing -> Should fail
    steps_fail = [MockStep("POST_Update", "POST", "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate")]
    report_fail = await engine.validate_workflow("wf_test", steps_fail, facts)
    assert report_fail.status == CompatibilityStatus.BLOCK
    assert len(report_fail.violations) == 1

    # 2. Both operations present -> Should pass
    steps_ok = [
        MockStep("GET_Firmware", "GET", "/redfish/v1/UpdateService/FirmwareInventory"),
        MockStep("POST_Update", "POST", "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate")
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
    from src.core.compatibility.models import CapabilityInfo, CompatibilityDomain, RiskLevel
    
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
        risk_profile_id="default_config_change"
    )
    profile_cap = await provider.get_risk_profile_for_capability(cap)
    assert profile_cap.id == "default_config_change"


@pytest.mark.asyncio
async def test_capability_discovery_service():
    from src.core.compatibility.engine import CapabilityDiscoveryService
    from src.core.compatibility.models import CompatibilityDomain, RiskLevel
    
    class MockRepo:
        def __init__(self):
            self.session_factory = None
        async def get_capability_by_operation(self, op_id):
            return None
            
    service = CapabilityDiscoveryService(MockRepo())
    async def mock_save(cap_info):
        pass
    service.save_candidate_capability = mock_save
    
    endpoints = [{
        "operation_id": "POST_SimpleUpdate",
        "method": "POST",
        "url": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "request_schema": {}
    }]
    
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
