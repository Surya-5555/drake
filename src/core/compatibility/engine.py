import logging
import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx

from src.core.compatibility.models import (
    CompatibilityFinding,
    CompatibilityViolation,
    CompatibilityReport,
    CompatibilityStatus,
    DeviceFacts,
    CompatibilityDomain,
    RiskLevel,
    CapabilityInfo,
)
from src.core.compatibility.repository import (
    CompatibilityRepository,
    RiskProfileProvider,
    RiskProfileRepository,
)
from src.core.database import async_session

logger = logging.getLogger(__name__)


def compare_versions(v1: str, v2: str) -> int:
    """
    Compares two version strings (e.g., '2.12.0' vs '2.1.2').
    Returns:
       -1 if v1 < v2
        0 if v1 == v2
        1 if v1 > v2
    """

    def clean_and_split(v: str) -> List[int]:
        cleaned = v.split("-")[0]
        parts = []
        for part in cleaned.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return parts

    parts1 = clean_and_split(v1)
    parts2 = clean_and_split(v2)

    max_len = max(len(parts1), len(parts2))
    parts1 += [0] * (max_len - len(parts1))
    parts2 += [0] * (max_len - len(parts2))

    for p1, p2 in zip(parts1, parts2):
        if p1 < p2:
            return -1
        elif p1 > p2:
            return 1
    return 0


class OperationCapabilityResolver:
    """
    Database-driven capability resolver that maps operation IDs to capabilities.
    """

    def __init__(self, repository: CompatibilityRepository):
        self.repository = repository

    async def resolve_operation_capability(
        self, operation_id: str
    ) -> Optional[CapabilityInfo]:
        """Lookup capability details dynamically from the registry."""
        return await self.repository.get_capability_by_operation(operation_id)


class CapabilityDiscoveryService:
    """
    Service that dynamically parses OpenAPI endpoints and registers candidates in the database.
    """

    def __init__(self, repository: Optional[CompatibilityRepository] = None):
        self.repository = repository or CompatibilityRepository()

    async def discover_capabilities(
        self, endpoints: List[Dict[str, Any]]
    ) -> List[CapabilityInfo]:
        """
        Processes ingested endpoints, classifies them into candidate capabilities,
        and saves them if no manual override is active.
        """
        discovered_caps = []
        for ep in endpoints:
            operation_id = ep["operation_id"]
            method = ep["method"].upper()
            url = ep["url"]

            existing_cap = await self.repository.get_capability_by_operation(
                operation_id
            )
            if existing_cap and existing_cap.is_manual_override:
                discovered_caps.append(existing_cap)
                continue

            domain = CompatibilityDomain.HARDWARE
            risk_level = RiskLevel.READ_ONLY
            cap_name = "GENERIC_QUERY"
            profile_id = "default_read_only"

            if (
                "UpdateService.SimpleUpdate" in url
                or "UpdateService.Install" in url
                or "SimpleUpdate" in operation_id
            ):
                domain = CompatibilityDomain.FIRMWARE
                risk_level = RiskLevel.DESTRUCTIVE
                cap_name = "FIRMWARE_UPDATE"
                profile_id = "default_destructive"
            elif (
                "UpdateService" in url
                or "SoftwareInventory" in url
                or "FirmwareInventory" in url
            ):
                domain = CompatibilityDomain.FIRMWARE
                risk_level = RiskLevel.READ_ONLY
                cap_name = "FIRMWARE_QUERY"
                profile_id = "default_read_only"
            elif "Systems" in url and "Reset" in url:
                domain = CompatibilityDomain.POWER
                risk_level = RiskLevel.DESTRUCTIVE
                cap_name = "POWER_CONTROL"
                profile_id = "default_destructive"
            elif "Systems" in url and method in ("PATCH", "PUT"):
                domain = CompatibilityDomain.BIOS
                risk_level = RiskLevel.CONFIG_CHANGE
                cap_name = "BIOS_UPDATE"
                profile_id = "default_config_change"
            elif "Systems" in url:
                domain = CompatibilityDomain.BIOS
                risk_level = RiskLevel.READ_ONLY
                cap_name = "BIOS_QUERY"
                profile_id = "default_read_only"
            elif "Chassis" in url and "Power" in url:
                domain = CompatibilityDomain.POWER
                risk_level = RiskLevel.READ_ONLY
                cap_name = "POWER_QUERY"
                profile_id = "default_read_only"
            elif "Chassis" in url:
                domain = CompatibilityDomain.HARDWARE
                risk_level = RiskLevel.READ_ONLY
                cap_name = "CHASSIS_QUERY"
                profile_id = "default_read_only"
            elif "Storage" in url:
                domain = CompatibilityDomain.STORAGE
                risk_level = (
                    RiskLevel.CONFIG_CHANGE
                    if method in ("POST", "PATCH", "DELETE")
                    else RiskLevel.READ_ONLY
                )
                cap_name = (
                    "STORAGE_CONTROL"
                    if method in ("POST", "PATCH", "DELETE")
                    else "STORAGE_QUERY"
                )
                profile_id = (
                    "default_config_change"
                    if method in ("POST", "PATCH", "DELETE")
                    else "default_read_only"
                )
            elif method == "GET":
                domain = CompatibilityDomain.HARDWARE
                risk_level = RiskLevel.READ_ONLY
                cap_name = "GENERIC_QUERY"
                profile_id = "default_read_only"
            else:
                domain = CompatibilityDomain.GOVERNANCE
                risk_level = RiskLevel.CONFIG_CHANGE
                cap_name = "GENERIC_CHANGE"
                profile_id = "default_config_change"

            cap_info = CapabilityInfo(
                operation_id=operation_id,
                capability_name=cap_name,
                compatibility_domain=domain,
                default_risk_level=risk_level,
                parameters_schema=ep.get("request_schema")
                if isinstance(ep.get("request_schema"), dict)
                else {},
                risk_profile_id=profile_id,
                is_manual_override=0,
                discovery_confidence=0.8 if existing_cap else 1.0,
            )

            await self.save_candidate_capability(cap_info)
            discovered_caps.append(cap_info)

        return discovered_caps

    async def save_candidate_capability(self, cap_info: CapabilityInfo) -> None:
        async with self.repository.session_factory() as session:
            from sqlalchemy import select
            from src.core.database import CapabilityRegistry as DBCapability

            result = await session.execute(
                select(DBCapability).where(
                    DBCapability.operation_id == cap_info.operation_id
                )
            )
            db_cap = result.scalar_one_or_none()
            if not db_cap:
                db_cap = DBCapability(
                    operation_id=cap_info.operation_id,
                    capability_name=cap_info.capability_name,
                    compatibility_domain=cap_info.compatibility_domain.value,
                    default_risk_level=cap_info.default_risk_level.value,
                    parameters_schema=json.dumps(cap_info.parameters_schema),
                    risk_profile_id=cap_info.risk_profile_id,
                    is_manual_override=cap_info.is_manual_override,
                    discovery_confidence=cap_info.discovery_confidence,
                )
                session.add(db_cap)
            else:
                if db_cap.is_manual_override == 0:
                    db_cap.capability_name = cap_info.capability_name
                    db_cap.compatibility_domain = cap_info.compatibility_domain.value
                    db_cap.default_risk_level = cap_info.default_risk_level.value
                    db_cap.parameters_schema = json.dumps(cap_info.parameters_schema)
                    db_cap.risk_profile_id = cap_info.risk_profile_id
                    db_cap.discovery_confidence = cap_info.discovery_confidence
            await session.commit()


class BlastRadiusEngine:
    """
    Scope-aware explainable blast radius engine using NetworkX graph topology and capabilities.
    """

    def __init__(self, repository: Optional[CompatibilityRepository] = None):
        self.repository = repository or CompatibilityRepository()

    async def calculate_blast_radius(
        self, workflow_steps: List[Any], domains: Set[str]
    ) -> Tuple[str, str]:
        """
        Determines the containment boundary and provides a clear, explainable reason.
        """
        if "GOVERNANCE" in domains:
            return (
                "CLUSTER",
                "Workflow executes platform governance operations affecting cluster-wide compliance.",
            )

        if "POWER" in domains or "STORAGE" in domains:
            has_cross_links = False
            try:
                edges = await self.repository.get_dependencies()
                if len(edges) > 5:
                    has_cross_links = True
            except Exception:
                pass

            if has_cross_links:
                return (
                    "RACK",
                    "Workflow targets power/storage operations with active cross-node dependencies.",
                )
            return (
                "CHASSIS",
                "Workflow modifies shared chassis components (Power/Storage controllers).",
            )

        if "BIOS" in domains or "FIRMWARE" in domains:
            return (
                "CHASSIS",
                "Workflow applies BIOS/Firmware updates affecting system hardware state.",
            )

        return (
            "NODE",
            "Workflow performs read-only operations restricted to a single server node.",
        )


class DependencyGraphEngine:
    """
    Builds and traverses Directed Acyclic Graphs (DAGs) representing rules and operations prerequisites.
    """

    def __init__(self, repository: CompatibilityRepository):
        self.repository = repository

    async def build_dependencies_dag(self) -> nx.DiGraph:
        """Constructs a Directed Graph of compatibility rules based on database associations."""
        dag = nx.DiGraph()

        rules = await self.repository.get_active_rules()
        for rule in rules:
            dag.add_node(rule["id"], **rule)

        edges = await self.repository.get_dependencies()
        for rule_id, prereq_id in edges:
            if dag.has_node(rule_id) and dag.has_node(prereq_id):
                dag.add_edge(prereq_id, rule_id)

        return dag

    def get_execution_order(self, dag: nx.DiGraph) -> List[str]:
        """Performs a topological sort to resolve execution hierarchy."""
        try:
            return list(nx.topological_sort(dag))
        except nx.NetworkXUnfeasible:
            logger.error("Circular dependency detected in rules configurations!")
            return list(dag.nodes())

    def generate_mermaid_diagram(self, dag: nx.DiGraph) -> str:
        """Outputs a Mermaid flowchart string representing dependency mapping."""
        lines = ["graph TD"]
        for u, v in dag.edges():
            u_label = dag.nodes[u].get("rule_name", u)
            v_label = dag.nodes[v].get("rule_name", v)
            lines.append(f'    node_{u}["{u_label}"] --> node_{v}["{v_label}"]')

        for node in dag.nodes():
            if dag.degree(node) == 0:
                label = dag.nodes[node].get("rule_name", node)
                lines.append(f'    node_{node}["{label}"]')
        return "\n".join(lines)

    def build_operations_dag(self, active_rules: List[Dict[str, Any]]) -> nx.DiGraph:
        """Constructs a Directed Graph of operation dependencies defined in dependency rules."""
        g = nx.DiGraph()
        for rule in active_rules:
            if rule["rule_type"] == "dependency":
                config = rule["rule_config"]
                prereq = config.get("prerequisite_operation_id")
                target = config.get("target_operation_id")
                if prereq and target:
                    g.add_node(prereq)
                    g.add_node(target)
                    g.add_edge(prereq, target)
        return g

    def verify_execution_order(
        self, dag: nx.DiGraph, workflow_steps: List[Any]
    ) -> List[Tuple[str, str]]:
        """
        Verifies if the workflow steps respect the topological order defined by the DAG.
        Returns a list of violations (prereq_op, target_op) that are violated.
        """
        op_indices = {}
        for idx, step in enumerate(workflow_steps):
            if step.operation_id not in op_indices:
                op_indices[step.operation_id] = idx

        violations = []
        for u, v in dag.edges():
            if v in op_indices:
                if u not in op_indices:
                    violations.append((u, v))
                elif op_indices[u] >= op_indices[v]:
                    violations.append((u, v))
        return violations


class CompatibilityEngine:
    """
    Core verification services engine that validates dynamic device compatibility.
    """

    def __init__(self, repository: CompatibilityRepository):
        self.repository = repository
        self.dag_engine = DependencyGraphEngine(repository)
        self.resolver = OperationCapabilityResolver(repository)

    async def validate_workflow(
        self,
        workflow_id: str,
        steps: List[Any],
        target_facts: DeviceFacts,
        as_of: Optional[datetime] = None,
    ) -> CompatibilityReport:
        logger.info(
            f"Evaluating compatibility of workflow {workflow_id} against IP {target_facts.target_ip}..."
        )

        findings: List[CompatibilityFinding] = []
        violations: List[CompatibilityViolation] = []

        resolved_domains: Set[str] = set()
        step_operation_ids: Set[str] = set()
        step_operation_ids_list: List[str] = []
        default_risk_levels: List[RiskLevel] = []

        for step in steps:
            op_id = step.operation_id
            step_operation_ids.add(op_id)
            step_operation_ids_list.append(op_id)

            cap = await self.resolver.resolve_operation_capability(op_id)
            if cap:
                resolved_domains.add(cap.compatibility_domain.value)
                default_risk_levels.append(cap.default_risk_level)
            else:
                if "UpdateService" in step.url:
                    resolved_domains.add("FIRMWARE")
                    default_risk_levels.append(RiskLevel.CONFIG_CHANGE)
                elif "Systems" in step.url:
                    resolved_domains.add("BIOS")
                    default_risk_levels.append(RiskLevel.READ_ONLY)
                else:
                    resolved_domains.add("HARDWARE")
                    default_risk_levels.append(RiskLevel.READ_ONLY)

        active_rules = []
        for domain in resolved_domains:
            domain_rules = await self.repository.get_rules_for_domain(
                domain, as_of=as_of
            )
            active_rules.extend(domain_rules)

        for rule in active_rules:
            rule_id = rule["id"]
            rule_type = rule["rule_type"]
            config = rule["rule_config"]

            if rule_type == "hardware":
                supported = config.get("supported_models", [])
                if target_facts.device_model not in supported:
                    violations.append(
                        CompatibilityViolation(
                            rule_id=rule_id,
                            field_checked="device_model",
                            expected_value=f"One of: {supported}",
                            actual_value=target_facts.device_model,
                            remediation_step=f"Hardware platform '{target_facts.device_model}' is not certified.",
                        )
                    )
                    findings.append(
                        CompatibilityFinding(
                            title="Hardware Model Certification Mismatch",
                            severity="critical",
                            message=f"Server model '{target_facts.device_model}' is not present in hardware catalog.",
                            suggested_action="Perform validation on compatible R750/R650 platform chassis.",
                        )
                    )

            elif rule_type == "bios":
                target_model = config.get("device_model")
                if target_model == target_facts.device_model:
                    min_bios = config.get("min_bios_version", "1.0.0")
                    if compare_versions(target_facts.bios_version, min_bios) < 0:
                        violations.append(
                            CompatibilityViolation(
                                rule_id=rule_id,
                                field_checked="bios_version",
                                expected_value=f">= {min_bios}",
                                actual_value=target_facts.bios_version,
                                remediation_step=f"Upgrade BIOS version to at least {min_bios}.",
                            )
                        )
                        findings.append(
                            CompatibilityFinding(
                                title="Legacy BIOS Version Detected",
                                severity="high",
                                message=f"System BIOS '{target_facts.bios_version}' is below required minimum threshold '{min_bios}'.",
                                suggested_action=f"Schedule system update task to install BIOS release >= {min_bios}.",
                            )
                        )

            elif rule_type == "firmware":
                component = config.get("target_component")
                min_fw = config.get("min_version")

                fw_version = None
                for name, ver in target_facts.firmware_inventory.items():
                    if component.lower() in name.lower():
                        fw_version = ver
                        break

                if fw_version:
                    if compare_versions(fw_version, min_fw) < 0:
                        violations.append(
                            CompatibilityViolation(
                                rule_id=rule_id,
                                field_checked=f"firmware_version.{component}",
                                expected_value=f">= {min_fw}",
                                actual_value=fw_version,
                                remediation_step=f"Update component {component} firmware version to at least {min_fw}.",
                            )
                        )
                        findings.append(
                            CompatibilityFinding(
                                title=f"Legacy Component Firmware ({component})",
                                severity="medium",
                                message=f"Installed version '{fw_version}' is below compatibility catalog base '{min_fw}'.",
                                suggested_action=f"Apply firmware patch to target {component} controller.",
                            )
                        )

            elif rule_type == "dependency":
                prereq_op = config.get("prerequisite_operation_id")
                target_op = config.get("target_operation_id")

                if target_op in step_operation_ids:
                    if prereq_op not in step_operation_ids:
                        violations.append(
                            CompatibilityViolation(
                                rule_id=rule_id,
                                field_checked="workflow_steps",
                                expected_value=f"Contains {prereq_op} before {target_op}",
                                actual_value="Prerequisite operation is missing in workflow steps sequence",
                                remediation_step=f"Ensure steps include '{prereq_op}' query before executing '{target_op}'.",
                            )
                        )
                        findings.append(
                            CompatibilityFinding(
                                title="Missing Step Dependency Prerequisite",
                                severity="high",
                                message=f"Operation '{target_op}' is ordered without prerequisite validation step '{prereq_op}'.",
                                suggested_action="Re-cluster or modify workflow steps sequence to query status before trigger.",
                            )
                        )
                    elif step_operation_ids_list.index(
                        prereq_op
                    ) >= step_operation_ids_list.index(target_op):
                        violations.append(
                            CompatibilityViolation(
                                rule_id=rule_id,
                                field_checked="workflow_steps",
                                expected_value=f"Contains {prereq_op} before {target_op}",
                                actual_value="Prerequisite operation is executed after or at the same time as target",
                                remediation_step=f"Re-order workflow steps to execute '{prereq_op}' before '{target_op}'.",
                            )
                        )
                        findings.append(
                            CompatibilityFinding(
                                title="Invalid Step Dependency Ordering",
                                severity="high",
                                message=f"Operation '{target_op}' is executed before prerequisite step '{prereq_op}'.",
                                suggested_action="Re-order workflow steps sequence to execute prerequisite before target.",
                            )
                        )

            elif rule_type == "safety":
                forbidden = config.get("forbidden_combinations", [])
                intersection = step_operation_ids.intersection(forbidden)
                if len(intersection) >= 2:
                    violations.append(
                        CompatibilityViolation(
                            rule_id=rule_id,
                            field_checked="workflow_safety",
                            expected_value="No safety conflicts",
                            actual_value=f"Conflict combination sequence: {list(intersection)}",
                            remediation_step="De-duplicate or isolate forbidden execution sequences.",
                        )
                    )
                    findings.append(
                        CompatibilityFinding(
                            title="Workflow Safety Sequence Conflict",
                            severity="critical",
                            message=f"Workflow contains dangerous forbidden operations combinations: {list(intersection)}.",
                            suggested_action="Separate target steps into standalone approved execution operations.",
                        )
                    )

        # Risk Score Calculation (Dynamic using RiskProfileProvider)
        session_factory = (
            getattr(self.repository, "session_factory", None) or async_session
        )
        profile_provider = RiskProfileProvider(RiskProfileRepository(session_factory))
        step_risks = []
        for idx, step in enumerate(steps):
            op_id = step.operation_id
            cap = await self.resolver.resolve_operation_capability(op_id)
            if cap:
                profile = await profile_provider.get_risk_profile_for_capability(cap)
            else:
                profile_id = "default_read_only"
                if "UpdateService" in step.url:
                    profile_id = "default_destructive"
                elif "Systems" in step.url:
                    profile_id = "default_read_only"
                profile = await profile_provider.get_risk_profile(profile_id)

            base_weights = {
                RiskLevel.READ_ONLY: 10,
                RiskLevel.CONFIG_CHANGE: 50,
                RiskLevel.DESTRUCTIVE: 90,
            }
            base_w = base_weights.get(profile.base_risk_level, 10)

            method_adj = profile.method_adjustments.get(step.method.upper(), 0)
            order_adj = (idx + 1) * profile.order_coefficient

            step_risk = min(base_w + method_adj + order_adj, profile.max_risk_score)
            step_risks.append(step_risk)

        risk_score = int(max(step_risks)) if step_risks else 10

        # Blast Radius Engine execution
        blast_radius_engine = BlastRadiusEngine(self.repository)
        (
            blast_radius,
            blast_radius_reason,
        ) = await blast_radius_engine.calculate_blast_radius(steps, resolved_domains)

        if blast_radius in ("CHASSIS", "RACK", "CLUSTER"):
            findings.append(
                CompatibilityFinding(
                    title=f"High Blast Radius Containment Alert: {blast_radius}",
                    severity="high" if blast_radius == "CHASSIS" else "critical",
                    message=f"Workflow execution profile triggers systemic impacts: {blast_radius_reason}",
                    suggested_action="Ensure administrative oversight and confirm fallback topology isolation boundaries.",
                )
            )

        # Confidence score calculation (freshness)
        confidence_score = 100
        if not target_facts.is_live:
            age_sec = 0.0
            if target_facts.last_scanned:
                last_scanned = target_facts.last_scanned
                if last_scanned.tzinfo is None:
                    last_scanned = last_scanned.replace(tzinfo=timezone.utc)
                age_sec = (datetime.now(timezone.utc) - last_scanned).total_seconds()

            if age_sec > 300:  # Expired cache fallback
                confidence_score = 40
                findings.append(
                    CompatibilityFinding(
                        title="Stale Device Inventory Cache",
                        severity="medium",
                        message=f"Target facts cache is stale (age: {int(age_sec)}s). Live pre-flight check recommended.",
                        suggested_action="Refresh facts cache before execution.",
                    )
                )
            else:  # Cached facts within TTL
                confidence_score = 80
        else:
            confidence_score = 100

        # Define overall status based on violations severity
        compatibility_score = max(0, 100 - (len(violations) * 25))
        status = CompatibilityStatus.ALLOW
        if violations:
            critical_finding = any(f.severity in ("critical", "high") for f in findings)
            if critical_finding or compatibility_score <= 50:
                status = CompatibilityStatus.BLOCK
            else:
                status = CompatibilityStatus.WARN

        return CompatibilityReport(
            id=f"rep_{uuid.uuid4().hex[:8]}",
            workflow_id=workflow_id,
            target_ip=target_facts.target_ip,
            status=status,
            compatibility_score=compatibility_score,
            risk_score=risk_score,
            blast_radius=blast_radius,
            confidence_score=confidence_score,
            findings=findings,
            violations=violations,
            timestamp=datetime.utcnow(),
        )
