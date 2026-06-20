from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class RuntimeGovernance:
    """Enforces runtime policies during execution."""
    
    def __init__(self, policy_config: Dict[str, Any]):
        self.config = policy_config
        self.limits = self.config.get("limits", {})
        self.security = self.config.get("security", {})
        self.mask_fields = set(self.security.get("mask_fields", ["password", "token", "secret"]))

    def mask_secrets(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Masks sensitive fields and automatically detects PII via Regex in the execution parameters for logging."""
        import re
        
        # Advanced regex patterns for PII detection
        pii_patterns = [
            # SSN
            r"\b\d{3}-\d{2}-\d{4}\b",
            # Credit Card (Basic numeric sequence, usually 13-16 digits)
            r"\b(?:\d[ -]*?){13,16}\b",
            # Standard Bearer Token / JWT
            r"Bearer\s+[a-zA-Z0-9\-\._~+/]+={0,2}",
            r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"
        ]
        
        def mask_string(val: str) -> str:
            for pattern in pii_patterns:
                val = re.sub(pattern, "[REDACTED_PII]", val)
            return val

        masked = {}
        for k, v in params.items():
            # Check if any masked keyword is in the key
            if any(m in k.lower() for m in self.mask_fields):
                masked[k] = "********"
            elif isinstance(v, dict):
                masked[k] = self.mask_secrets(v)
            elif isinstance(v, list):
                masked[k] = [self.mask_secrets(i) if isinstance(i, dict) else (mask_string(str(i)) if isinstance(i, str) else i) for i in v]
            elif isinstance(v, str):
                masked[k] = mask_string(v)
            else:
                masked[k] = v
        return masked
    def validate_execution(self, workflow_name: str, params: Dict[str, Any]) -> None:
        """
        Validates execution preconditions like rate limiting and payload validation.
        Raises an exception if execution should be blocked.
        """
        # Rate limit and circuit breaker stubs would go here
        pass

    def intercept(self, workflow_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pre-execution hook. Returns masked params for safe logging.
        """
        self.validate_execution(workflow_name, params)
        masked_params = self.mask_secrets(params)
        return masked_params
