import yaml
from pathlib import Path
from typing import Dict, Any, List

class PolicyEngine:
    """Evaluates workflows against governance policies defined in policy.yaml."""

    def __init__(self, policy_path: str = None):
        if not policy_path:
            policy_path = str(Path(__file__).resolve().parent.parent / "config" / "policy.yaml")
        
        self.config = self._load_policy(policy_path)
        self.rules = self.config.get("rules", [])

    def _load_policy(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            # Fallback to empty if not found, let defaults handle it
            return {}

    def get_config(self) -> Dict[str, Any]:
        return self.config

    def evaluate(self, workflow_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates the workflow context against rules.
        workflow_context should contain 'risk_level', 'is_read_only', 'actions', 'is_bulk', etc.
        Returns: {"status": 0|1|2, "reason": str}
        where 0 = Pending, 1 = Approved, 2 = Rejected
        """
        # Default to pending
        result_status = 0
        rejection_reason = None

        # Build local scope for eval
        eval_locals = {
            "workflow": type("WorkflowContext", (), workflow_context)()
        }

        for rule in self.rules:
            condition_expr = rule.get("condition", "False")
            action = rule.get("action")
            
            try:
                # Evaluate the condition safely
                is_match = eval(condition_expr, {"__builtins__": {}}, eval_locals)
                if is_match:
                    if action == "DENY":
                        return {"status": 2, "reason": rule.get("reason", "Denied by policy rule: " + rule.get("name", ""))}
                    elif action == "AUTO_APPROVE":
                        result_status = 1
                    elif action == "REQUIRE_APPROVAL":
                        result_status = 0
            except Exception as e:
                # Log or handle eval errors
                pass

        return {"status": result_status, "reason": rejection_reason}
