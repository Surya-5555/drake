from typing import Dict, Any, List

class RiskAssessor:
    """Classifies risk levels of workflows based on actions and keywords."""

    def __init__(self, policy_config: Dict[str, Any]):
        self.config = policy_config.get("risk_classification", {})
        self.high_risk_methods = set(self.config.get("high_risk_methods", ["DELETE", "PATCH", "PUT"]))
        self.high_risk_keywords = set(self.config.get("high_risk_keywords", ["reboot", "power", "firmware", "reset", "format"]))
        self.read_only_methods = set(self.config.get("read_only_methods", ["GET", "HEAD"]))

    def assess_risk(self, endpoints: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes a list of endpoints and determines the risk level, risk score, and governance score.
        Returns a dict with 'risk_level', 'is_read_only', 'risk_score', 'governance_score', 'risk_explanation'.
        """
        if not endpoints:
            return {
                "risk_level": "LOW", 
                "is_read_only": True, 
                "risk_score": 0.0, 
                "governance_score": 100.0, 
                "risk_explanation": "Empty workflow"
            }

        risk_score = 0.0
        explanations = []
        has_schemas = True

        for ep in endpoints:
            method = ep.get("method", "").upper()
            url = ep.get("url", "").lower()
            
            # Simple check for schemas if available (for governance score)
            if "request_schema" in ep and not ep.get("request_schema") and not ep.get("response_schema"):
                has_schemas = False

            if method == "DELETE":
                risk_score += 50.0
                explanations.append(f"Contains DELETE method for {url} (+50)")
            elif method in ["PATCH", "PUT"]:
                risk_score += 30.0
                explanations.append(f"Contains {method} method for {url} (+30)")
            elif method in ["POST"]:
                risk_score += 20.0
                explanations.append(f"Contains POST method for {url} (+20)")
                
            for keyword in self.high_risk_keywords:
                if keyword in url:
                    risk_score += 40.0
                    explanations.append(f"Contains high-risk keyword '{keyword}' in {url} (+40)")

        # Cap risk score at 100
        risk_score = min(risk_score, 100.0)
        
        methods = {ep.get("method", "").upper() for ep in endpoints}
        is_read_only = all(m in self.read_only_methods for m in methods)
        
        if is_read_only:
            risk_level = "LOW"
            if risk_score == 0.0:
                explanations.append("Workflow is read-only")
        elif risk_score >= 50.0:
            risk_level = "HIGH"
        elif risk_score >= 20.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
            
        # Governance Score (0-100)
        # Base is 100. Deduct for high risk. Deduct if missing schemas. Add for well documented.
        gov_score = 100.0 - (risk_score * 0.5)
        if not has_schemas:
            gov_score -= 20.0
            explanations.append("Missing request/response schemas (-20 gov score)")
            
        if is_read_only:
            gov_score = min(gov_score + 10.0, 100.0)

        gov_score = max(0.0, min(100.0, gov_score))
        
        return {
            "risk_level": risk_level,
            "is_read_only": is_read_only,
            "risk_score": float(risk_score),
            "governance_score": float(gov_score),
            "risk_explanation": "; ".join(explanations)
        }
