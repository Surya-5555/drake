import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.cli.exceptions import DellCLIError
from src.core.database import async_session, Workflow
from src.core.compatibility.repository import CompatibilityRepository
from src.core.compatibility.engine import CompatibilityEngine
from src.core.compatibility.sources import (
    RedfishFactsProvider,
    CachedFactsProvider,
    StaticFactsProvider,
)
from .bridge import AsyncServiceBridge


class CompatibilityCLIService:
    """Adapter for rules validation, explanations, and device inventory."""

    def validate_workflow(
        self, workflow_id: str, target_ip: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Any]:
        async def _async_validate() -> Tuple[Dict[str, Any], Dict[str, Any], Any]:
            async with async_session() as session:
                result = await session.execute(
                    select(Workflow)
                    .where(Workflow.id == workflow_id)
                    .options(selectinload(Workflow.steps))
                )
                wf = result.scalar_one_or_none()
                if not wf:
                    raise DellCLIError(
                        title="Validation Failure",
                        cause=f"Workflow '{workflow_id}' not found.",
                        impact="Pre-flight checks cannot compile scores.",
                        action="Ensure ID is correct and approved.",
                    )
                steps = wf.steps

            repo = CompatibilityRepository()  # type: ignore[no-untyped-call]
            engine = CompatibilityEngine(repo)

            # Query device facts with fallback
            try:
                facts = await RedfishFactsProvider(
                    base_url=os.getenv("PRISM_URL", "http://localhost:4010")
                ).get_device_facts(target_ip)
                facts.is_live = True
            except Exception:
                try:
                    facts = await CachedFactsProvider().get_device_facts(target_ip)
                    facts.is_live = False
                except Exception:
                    facts = await StaticFactsProvider().get_device_facts(target_ip)
                    facts.is_live = False

            await repo.save_device_facts(facts)

            report = await engine.validate_workflow(str(wf.id), steps, facts)
            await repo.save_report(report)

            # Retrieve rule DAG dependency details
            dag = await engine.dag_engine.build_dependencies_dag()
            dag_nodes_edges = (
                [dict(dag.nodes[node]) for node in dag.nodes()],
                list(dag.edges()),
            )

            report_data = {
                "id": report.id,
                "workflow_id": report.workflow_id,
                "target_ip": report.target_ip,
                "status": report.status.value,
                "compatibility_score": report.compatibility_score,
                "risk_score": report.risk_score,
                "blast_radius": report.blast_radius,
                "confidence_score": report.confidence_score,
                "timestamp": report.timestamp.isoformat()
                if report.timestamp
                else datetime.now(timezone.utc).isoformat(),
                "findings": [f.model_dump() for f in report.findings],
                "violations": [v.model_dump() for v in report.violations],
            }

            facts_data = {
                "target_ip": facts.target_ip,
                "device_model": facts.device_model,
                "bios_version": facts.bios_version,
                "lifecycle_controller_version": facts.lifecycle_controller_version,
                "last_scanned": facts.last_scanned.isoformat()
                if hasattr(facts.last_scanned, "isoformat") and facts.last_scanned
                else str(facts.last_scanned),
            }

            return report_data, facts_data, dag_nodes_edges

        return AsyncServiceBridge.run(_async_validate())  # type: ignore[no-any-return]

    def get_rules(self) -> List[Dict[str, Any]]:
        async def _async_get_rules() -> List[Dict[str, Any]]:
            repo = CompatibilityRepository()  # type: ignore[no-untyped-call]
            rules = await repo.get_active_rules()
            return [
                {
                    "id": r["id"],
                    "rule_name": r["rule_name"],
                    "rule_type": r["rule_type"],
                    "domain": r["domain"],
                    "rule_version": r["rule_version"],
                    "effective_from": r["effective_from"],
                }
                for r in rules
            ]

        return AsyncServiceBridge.run(_async_get_rules())  # type: ignore[no-any-return]

    def get_device_facts(self, ip: str) -> Dict[str, Any]:
        async def _async_get_facts() -> Dict[str, Any]:
            try:
                facts = await CachedFactsProvider().get_device_facts(ip)
                return {
                    "target_ip": facts.target_ip,
                    "device_model": facts.device_model,
                    "bios_version": facts.bios_version,
                    "lifecycle_controller_version": facts.lifecycle_controller_version,
                    "last_scanned": facts.last_scanned.isoformat()
                    if hasattr(facts.last_scanned, "isoformat") and facts.last_scanned
                    else str(facts.last_scanned),
                }
            except Exception:
                raise DellCLIError(
                    title="Device Query Failed",
                    cause=f"IP '{ip}' is not present in local states inventory cache.",
                    impact="Cached specifications cannot be retrieved.",
                    action="Validate device compatibility first to query Redfish details.",
                )

        return AsyncServiceBridge.run(_async_get_facts())  # type: ignore[no-any-return]
