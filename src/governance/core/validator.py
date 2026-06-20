from typing import Dict, Any, List

class WorkflowValidator:
    """Validates structural integrity and parameter mappings of generated workflows."""

    def validate(self, workflow: Dict[str, Any], endpoints: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validates the workflow structure.
        Returns a dict with 'is_valid' and 'errors' list.
        """
        errors = []
        
        # Simple structural validation
        if not workflow.get("id"):
            errors.append("Missing workflow id.")
            
        # Check endpoint completeness
        if not endpoints:
            errors.append("Workflow has no underlying endpoints.")
            
        # Cycle detection using DFS
        def has_cycle(edges: List[Dict[str, str]], nodes: List[str]) -> bool:
            adj = {n: [] for n in nodes}
            for e in edges:
                if e.get("source") in adj:
                    adj[e["source"]].append(e["target"])
            
            visited = set()
            rec_stack = set()
            
            def dfs(node):
                visited.add(node)
                rec_stack.add(node)
                for neighbor in adj.get(node, []):
                    if neighbor not in visited:
                        if dfs(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        return True
                rec_stack.remove(node)
                return False
                
            for node in nodes:
                if node not in visited:
                    if dfs(node):
                        return True
            return False

        # If the workflow contains explicit edge dependencies, check for cycles
        if "edges" in workflow:
            nodes = [ep.get("operation_id") for ep in endpoints if ep.get("operation_id")]
            if has_cycle(workflow["edges"], nodes):
                errors.append("Workflow dependency graph contains a cycle.")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }
