import logging
from typing import Dict, Any, List

from src.governance.core.policy import PolicyEngine
from src.governance.core.risk import RiskAssessor
from src.governance.core.validator import WorkflowValidator
from src.governance.runtime.interceptor import RuntimeGovernance

logger = logging.getLogger(__name__)

class GovernanceMiddleware:
    """Facade for the Governance Layer."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.validator = WorkflowValidator()
        self.risk_assessor = RiskAssessor(self.policy_engine.get_config())
        self.runtime = RuntimeGovernance(self.policy_engine.get_config())

    def process_new_workflows(self, workflows: List[Dict[str, Any]], endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Intercepts workflows before persistence.
        Applies validation, risk assessment, and policy rules.
        Modifies the 'approved' and 'risk_level' fields in place.
        """
        # Map endpoints by operation_id for quick lookup
        endpoint_map = {ep["operation_id"]: ep for ep in endpoints}

        for wf in workflows:
            wf_id = wf.get("id")
            comm_id = wf.get("community_id", wf_id)
            
            # Find underlying endpoints (assuming direct map or via community_id)
            underlying = [ep for ep in endpoints if ep.get("community_id") == comm_id or ep.get("operation_id") == wf_id]
            
            # 1. Validation
            val_result = self.validator.validate(wf, underlying)
            if not val_result["is_valid"]:
                wf["approved"] = 2 # Rejected
                wf["rejection_reason"] = "Validation failed: " + ", ".join(val_result["errors"])
                continue

            # 2. Risk Assessment
            risk_result = self.risk_assessor.assess_risk(underlying)
            wf["risk_level"] = risk_result["risk_level"]
            wf["risk_score"] = risk_result.get("risk_score", 0.0)
            wf["governance_score"] = risk_result.get("governance_score", 100.0)
            
            # Policy Version injection
            wf["policy_version"] = self.policy_engine.get_config().get("version", "1.0")
            
            # 3. Policy Evaluation
            actions = [ep.get("method", "").upper() for ep in underlying]
            context = {
                "risk_level": risk_result["risk_level"],
                "is_read_only": risk_result["is_read_only"],
                "actions": actions,
                "is_bulk": len(underlying) > 1,
            }
            
            policy_result = self.policy_engine.evaluate(context)
            
            # Only update approved status if the workflow wasn't manually set by user before
            # For new workflows, approved is likely 0 initially or not set
            if wf.get("approved", 0) == 0:
                wf["approved"] = policy_result["status"]
                wf["rejection_reason"] = policy_result["reason"] or risk_result.get("risk_explanation")
                
                status_str = {0: "PENDING", 1: "AUTO_APPROVED", 2: "DENIED"}.get(wf["approved"], "UNKNOWN")
                logger.info(f"Governance Middleware: Workflow {wf_id} classified as {wf['risk_level']}, state set to {status_str}")

        return workflows

    def intercept_execution(self, workflow_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runtime hook for execution.
        Raises exception if blocked, returns masked params.
        """
        logger.info(f"Governance Middleware: Intercepting execution for {workflow_name}")
        masked = self.runtime.intercept(workflow_name, params)
        return masked
