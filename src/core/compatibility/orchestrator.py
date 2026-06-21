import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.core.exceptions import DellProxyExecutionError
from src.core.database import async_session, Workflow, log_audit_event
from src.core.compatibility.models import CompatibilityStatus
from src.core.compatibility.repository import CompatibilityRepository
from src.core.compatibility.engine import CompatibilityEngine
from src.core.compatibility.sources import (
    RedfishFactsProvider,
    CachedFactsProvider,
    StaticFactsProvider,
    increment_cache_hits,
    increment_cache_misses,
)

logger = logging.getLogger(__name__)


class CompatibilityPolicyViolation(DellProxyExecutionError):
    """
    Exception raised when a compatibility validation failure blocks execution under STRICT policy.
    """

    def __init__(self, message: str, report: Any) -> None:
        self.report = report
        super().__init__(message)


class WorkflowExecutionManager:
    """
    Orchestrator interceptor that handles pre-flight validation, risk scoring,
    and cache lookup prior to triggering execution on targets.
    """

    def __init__(
        self,
        repository: Optional[CompatibilityRepository] = None,
        engine: Optional[CompatibilityEngine] = None,
    ):
        self.repository = repository or CompatibilityRepository()
        self.engine = engine or CompatibilityEngine(self.repository)

    async def execute_workflow_with_validation(
        self,
        workflow_name: str,
        params: Dict[str, Any],
        target_ip: Optional[str] = None,
        policy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validates target compatibility and executes steps under configured security policy.
        """
        if not policy:
            policy = os.getenv("DELL_COMPATIBILITY_POLICY", "STRICT").upper()

        if policy not in ("STRICT", "WARN_ONLY", "DISABLED"):
            policy = "STRICT"

        ip = (
            target_ip
            or params.get("target_ip")
            or params.get("system_id")
            or "192.168.0.120"
        )

        async with async_session() as session:
            result = await session.execute(
                select(Workflow)
                .where(Workflow.system_name == workflow_name)
                .options(selectinload(Workflow.steps))
            )
            wf = result.scalar_one_or_none()
            if not wf:
                raise DellProxyExecutionError(f"Workflow '{workflow_name}' not found.")
            steps = wf.steps

        report = None
        target_facts = None

        if policy != "DISABLED":
            facts_cache = CachedFactsProvider()
            redfish_provider = RedfishFactsProvider(
                base_url=os.getenv("PRISM_URL", "http://localhost:4010")
            )
            static_provider = StaticFactsProvider()

            use_live = True
            try:
                cached_facts = await facts_cache.get_device_facts(ip)
                if cached_facts.last_scanned:
                    last_scanned = cached_facts.last_scanned
                    if last_scanned.tzinfo is None:
                        last_scanned = last_scanned.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - last_scanned).total_seconds()
                    if age < 300:  # Cache hit & fresh
                        use_live = False
                        target_facts = cached_facts
                        target_facts.is_live = False
                        increment_cache_hits()
                        logger.info(f"Using fresh cached device facts for target {ip}.")
            except Exception:
                pass  # Cache miss

            if use_live:
                increment_cache_misses()
                try:
                    target_facts = await redfish_provider.get_device_facts(ip)
                    target_facts.is_live = True
                    await self.repository.save_device_facts(target_facts)
                except Exception as live_err:
                    logger.warning(
                        f"Live Redfish query failed for {ip}: {live_err}. Falling back to cache..."
                    )
                    try:
                        target_facts = await facts_cache.get_device_facts(ip)
                        target_facts.is_live = False
                    except Exception as cache_err:
                        logger.warning(
                            f"Cache lookup failed for {ip}: {cache_err}. Falling back to static mock."
                        )
                        target_facts = await static_provider.get_device_facts(ip)
                        target_facts.is_live = False

            report = await self.engine.validate_workflow(wf.id, steps, target_facts)

            # Auto live refresh check if used cached facts and confidence score is low (< 50)
            if not use_live and report and report.confidence_score < 50:
                logger.info(
                    "Confidence score is low due to stale cache. Triggering auto cache refresh via Redfish live query..."
                )
                try:
                    target_facts = await redfish_provider.get_device_facts(ip)
                    target_facts.is_live = True
                    await self.repository.save_device_facts(target_facts)
                    report = await self.engine.validate_workflow(
                        wf.id, steps, target_facts
                    )
                except Exception as refresh_err:
                    logger.warning(
                        f"Auto live cache refresh failed: {refresh_err}. Proceeding with current report state."
                    )

            await self.repository.save_report(report)

            # Enforce policy block on low confidence
            if report.confidence_score < 50 and policy in ("STRICT", "WARN_ONLY"):
                log_audit_event(
                    event_type="compatibility_blocked",
                    status="failed",
                    description=f"Execution blocked for workflow '{wf.display_name}' on target {ip} due to low confidence ({report.confidence_score}%). A live Redfish query is required.",
                    workflow_name=workflow_name,
                    actor="system",
                )
                raise CompatibilityPolicyViolation(
                    f"Execution blocked: confidence score ({report.confidence_score}%) is below policy threshold (50) under {policy} mode. A live Redfish query is required.",
                    report=report,
                )

            # Enforce standard compatibility status policy gates
            if report.status == CompatibilityStatus.BLOCK and policy == "STRICT":
                log_audit_event(
                    event_type="compatibility_blocked",
                    status="failed",
                    description=f"Execution blocked for workflow '{wf.display_name}' on target {ip} due to STRICT compatibility rules.",
                    workflow_name=workflow_name,
                    actor="system",
                )
                raise CompatibilityPolicyViolation(
                    f"STRICT Policy blocked execution of workflow '{workflow_name}' on target {ip} due to validation failures.",
                    report=report,
                )

            elif (
                report.status in (CompatibilityStatus.BLOCK, CompatibilityStatus.WARN)
                and policy == "WARN_ONLY"
            ):
                log_audit_event(
                    event_type="compatibility_warning",
                    status="success",
                    description=f"Compatibility warning issued for workflow '{wf.display_name}' on target {ip} under WARN_ONLY policy.",
                    workflow_name=workflow_name,
                    actor="system",
                )
            else:
                log_audit_event(
                    event_type="compatibility_checked",
                    status="success",
                    description=f"Compatibility validated successfully for workflow '{wf.display_name}' on target {ip}.",
                    workflow_name=workflow_name,
                    actor="system",
                )

        from src.proxy.executors.httpx_executor import PrismExecutor, MockExecutor
        from src.proxy.executors.dell_omsdk_executor import DellOMSDKExecutor

        executor_type = os.getenv("DELL_EXECUTOR_TYPE", "prism").lower()
        if executor_type == "omsdk":
            executor = DellOMSDKExecutor()
        elif executor_type == "prism":
            prism_url = os.getenv("PRISM_URL", "http://localhost:4010")
            executor = PrismExecutor(base_url=prism_url)
        else:
            mock_server_url = os.getenv("MOCK_SERVER_URL", "http://localhost:8000")
            executor = MockExecutor(base_url=mock_server_url)

        from src.proxy.executors.workflow_execution_service import (
            WorkflowExecutionService,
        )

        target_server_ip = (
            params.get("target_server_ip") or params.get("server_ip") or "127.0.0.1"
        )
        service = WorkflowExecutionService(executor)
        exec_res = await service.execute_workflow(
            workflow_name, target_server_ip, params
        )

        if report:
            exec_res["compatibility_assessment"] = {
                "report_id": report.id,
                "status": report.status.value,
                "compatibility_score": report.compatibility_score,
                "risk_score": report.risk_score,
                "blast_radius": report.blast_radius,
                "confidence_score": report.confidence_score,
                "findings": [f.model_dump() for f in report.findings],
                "violations": [v.model_dump() for v in report.violations],
                "timestamp": report.timestamp.isoformat(),
            }

        return exec_res
