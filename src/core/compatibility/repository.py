import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.future import select
from sqlalchemy import and_, or_

from src.core.compatibility.models import (
    CapabilityInfo,
    CompatibilityReport,
    DeviceFacts,
    CompatibilityDomain,
    RiskLevel,
    RiskProfile
)
from src.core.database import (
    async_session,
    CapabilityRegistry as DBCapability,
    CompatibilityRule as DBRule,
    CompatibilityDependency as DBDependency,
    DeviceInventory as DBDevice,
    CompatibilityReport as DBReport,
    RiskProfile as DBRiskProfile
)

logger = logging.getLogger(__name__)


class CompatibilityRepository:
    """
    SQLAlchemy database repository adapter for the compatibility intelligence data layer.
    """
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or async_session

    async def get_capabilities_registry(self) -> Dict[str, CapabilityInfo]:
        """Fetch all mapped dynamic operation capabilities."""
        async with self.session_factory() as session:
            result = await session.execute(select(DBCapability))
            db_caps = result.scalars().all()
            
            registry = {}
            for db_cap in db_caps:
                registry[db_cap.operation_id] = CapabilityInfo(
                    operation_id=db_cap.operation_id,
                    capability_name=db_cap.capability_name,
                    compatibility_domain=CompatibilityDomain(db_cap.compatibility_domain),
                    default_risk_level=RiskLevel(db_cap.default_risk_level),
                    parameters_schema=json.loads(db_cap.parameters_schema) if db_cap.parameters_schema else {}
                )
            return registry

    async def get_capability_by_operation(self, operation_id: str) -> Optional[CapabilityInfo]:
        """Lookup capability attributes by operation identifier."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(DBCapability).where(DBCapability.operation_id == operation_id)
            )
            db_cap = result.scalar_one_or_none()
            if not db_cap:
                return None
            return CapabilityInfo(
                operation_id=db_cap.operation_id,
                capability_name=db_cap.capability_name,
                compatibility_domain=CompatibilityDomain(db_cap.compatibility_domain),
                default_risk_level=RiskLevel(db_cap.default_risk_level),
                parameters_schema=json.loads(db_cap.parameters_schema) if db_cap.parameters_schema else {}
            )

    async def get_active_rules(self, as_of: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Query compatibility rules matching temporal activity boundaries (effective rules).
        Supports audit replays at a past datetime timestamp.
        """
        as_of_time = as_of or datetime.now(timezone.utc)
        if as_of_time.tzinfo is None:
            as_of_time = as_of_time.replace(tzinfo=timezone.utc)
        as_of_str = as_of_time.isoformat()

        async with self.session_factory() as session:
            # Match rules where effective_from <= as_of_str and (effective_to is null or effective_to > as_of_str)
            stmt = select(DBRule).where(
                and_(
                    DBRule.effective_from <= as_of_str,
                    or_(
                        DBRule.effective_to.is_(None),
                        DBRule.effective_to > as_of_str
                    )
                )
            )
            result = await session.execute(stmt)
            db_rules = result.scalars().all()
            
            rules = []
            for r in db_rules:
                rules.append({
                    "id": r.id,
                    "rule_name": r.rule_name,
                    "rule_type": r.rule_type,
                    "domain": r.domain,
                    "rule_version": r.rule_version,
                    "effective_from": r.effective_from,
                    "effective_to": r.effective_to,
                    "created_by": r.created_by,
                    "superseded_by": r.superseded_by,
                    "change_reason": r.change_reason,
                    "rule_config": json.loads(r.rule_config) if r.rule_config else {}
                })
            return rules

    async def get_rules_for_domain(self, domain: str, as_of: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Retrieve temporal rules filtered by compatibility domain."""
        as_of_time = as_of or datetime.now(timezone.utc)
        if as_of_time.tzinfo is None:
            as_of_time = as_of_time.replace(tzinfo=timezone.utc)
        as_of_str = as_of_time.isoformat()

        async with self.session_factory() as session:
            stmt = select(DBRule).where(
                and_(
                    DBRule.domain == domain,
                    DBRule.effective_from <= as_of_str,
                    or_(
                        DBRule.effective_to.is_(None),
                        DBRule.effective_to > as_of_str
                    )
                )
            )
            result = await session.execute(stmt)
            db_rules = result.scalars().all()
            
            rules = []
            for r in db_rules:
                rules.append({
                    "id": r.id,
                    "rule_name": r.rule_name,
                    "rule_type": r.rule_type,
                    "domain": r.domain,
                    "rule_version": r.rule_version,
                    "effective_from": r.effective_from,
                    "effective_to": r.effective_to,
                    "created_by": r.created_by,
                    "superseded_by": r.superseded_by,
                    "change_reason": r.change_reason,
                    "rule_config": json.loads(r.rule_config) if r.rule_config else {}
                })
            return rules

    async def get_dependencies(self) -> List[Tuple[str, str]]:
        """Fetch list of prerequisite update relationships links."""
        async with self.session_factory() as session:
            result = await session.execute(select(DBDependency))
            db_deps = result.all()
            return [(d[0].rule_id, d[0].prerequisite_rule_id) for d in db_deps]

    async def save_report(self, report: CompatibilityReport) -> None:
        """Archive a validation report details row."""
        async with self.session_factory() as session:
            db_report = DBReport(
                id=report.id,
                workflow_id=report.workflow_id,
                target_ip=report.target_ip,
                status=report.status.value,
                compatibility_score=report.compatibility_score,
                risk_score=report.risk_score,
                report_json=report.model_dump_json(),
                timestamp=report.timestamp.isoformat()
            )
            session.add(db_report)
            await session.commit()

    async def save_device_facts(self, facts: DeviceFacts) -> None:
        """Update hardware facts in device_inventory (stateful facts cache)."""
        async with self.session_factory() as session:
            # Check if exists
            result = await session.execute(
                select(DBDevice).where(DBDevice.target_ip == facts.target_ip)
            )
            device = result.scalar_one_or_none()

            last_scanned_str = facts.last_scanned.isoformat() if facts.last_scanned else datetime.now(timezone.utc).isoformat()
            firmware_json = json.dumps(facts.firmware_inventory)

            if not device:
                device = DBDevice(
                    id=f"dev_{int(datetime.now(timezone.utc).timestamp())}",
                    target_ip=facts.target_ip,
                    device_model=facts.device_model,
                    bios_version=facts.bios_version,
                    lifecycle_controller_version=facts.lifecycle_controller_version,
                    firmware_inventory=firmware_json,
                    last_scanned=last_scanned_str
                )
                session.add(device)
            else:
                device.device_model = facts.device_model
                device.bios_version = facts.bios_version
                device.lifecycle_controller_version = facts.lifecycle_controller_version
                device.firmware_inventory = firmware_json
                device.last_scanned = last_scanned_str

            await session.commit()

    async def get_reports_for_workflow(self, workflow_id: str) -> List[CompatibilityReport]:
        """Fetch report history for a specific workflow."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(DBReport).where(DBReport.workflow_id == workflow_id)
            )
            db_reports = result.scalars().all()
            
            reports = []
            for r in db_reports:
                try:
                    data = json.loads(r.report_json)
                    reports.append(CompatibilityReport.model_validate(data))
                except Exception:
                    pass
            return reports

    async def supersede_rule(self, old_rule_id: str, new_rule_data: Dict[str, Any]) -> str:
        """
        Updates the old rule's effective_to date and registers a new rule version.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        new_rule_id = new_rule_data.get("id") or f"rule_{int(datetime.now(timezone.utc).timestamp())}"
        
        async with self.session_factory() as session:
            result = await session.execute(
                select(DBRule).where(DBRule.id == old_rule_id)
            )
            old_rule = result.scalar_one_or_none()
            if old_rule:
                old_rule.effective_to = now_str
                old_rule.superseded_by = new_rule_id
            
            new_version = (old_rule.rule_version + 1) if old_rule else 1
            db_new_rule = DBRule(
                id=new_rule_id,
                rule_name=new_rule_data["rule_name"],
                rule_type=new_rule_data["rule_type"],
                domain=new_rule_data["domain"],
                rule_version=new_version,
                effective_from=now_str,
                effective_to=None,
                created_by=new_rule_data.get("created_by", "system"),
                superseded_by=None,
                change_reason=new_rule_data.get("change_reason", "Superseded older version"),
                rule_config=json.dumps(new_rule_data["rule_config"]) if isinstance(new_rule_data["rule_config"], dict) else new_rule_data["rule_config"]
            )
            session.add(db_new_rule)
            await session.commit()
            
        return new_rule_id


class RiskProfileRepository:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or async_session

    async def get_all_profiles(self) -> List[RiskProfile]:
        async with self.session_factory() as session:
            result = await session.execute(select(DBRiskProfile))
            db_profiles = result.scalars().all()
            return [
                RiskProfile(
                    id=db_p.id,
                    profile_name=db_p.profile_name,
                    base_risk_level=RiskLevel(db_p.base_risk_level),
                    method_adjustments=json.loads(db_p.method_adjustments) if db_p.method_adjustments else {},
                    order_coefficient=db_p.order_coefficient,
                    max_risk_score=db_p.max_risk_score
                )
                for db_p in db_profiles
            ]

    async def get_profile(self, profile_id: str) -> Optional[RiskProfile]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(DBRiskProfile).where(DBRiskProfile.id == profile_id)
            )
            db_p = result.scalar_one_or_none()
            if not db_p:
                return None
            return RiskProfile(
                id=db_p.id,
                profile_name=db_p.profile_name,
                base_risk_level=RiskLevel(db_p.base_risk_level),
                method_adjustments=json.loads(db_p.method_adjustments) if db_p.method_adjustments else {},
                order_coefficient=db_p.order_coefficient,
                max_risk_score=db_p.max_risk_score
            )


class RiskProfileProvider:
    def __init__(self, repository: Optional[RiskProfileRepository] = None):
        self.repository = repository or RiskProfileRepository()
        self.cache: Dict[str, RiskProfile] = {}

    async def get_risk_profile(self, profile_id: str) -> RiskProfile:
        if profile_id in self.cache:
            return self.cache[profile_id]
        
        profile = await self.repository.get_profile(profile_id)
        if not profile:
            fallback_map = {
                "default_read_only": RiskProfile(id="default_read_only", profile_name="Default Read-Only", base_risk_level=RiskLevel.READ_ONLY, method_adjustments={}, order_coefficient=0.0, max_risk_score=100),
                "default_config_change": RiskProfile(id="default_config_change", profile_name="Default Config Change", base_risk_level=RiskLevel.CONFIG_CHANGE, method_adjustments={"POST": 5, "PUT": 10, "PATCH": 5}, order_coefficient=1.0, max_risk_score=100),
                "default_destructive": RiskProfile(id="default_destructive", profile_name="Default Destructive", base_risk_level=RiskLevel.DESTRUCTIVE, method_adjustments={"POST": 10, "PUT": 15, "DELETE": 20}, order_coefficient=2.0, max_risk_score=100)
            }
            profile = fallback_map.get(profile_id, fallback_map["default_read_only"])
        self.cache[profile_id] = profile
        return profile

    async def get_risk_profile_for_capability(self, capability: CapabilityInfo) -> RiskProfile:
        profile_id = capability.risk_profile_id or "default_read_only"
        return await self.get_risk_profile(profile_id)
