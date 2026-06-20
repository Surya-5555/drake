import json
import logging
import networkx as nx
from typing import List, Dict, Any, Set

logger = logging.getLogger(__name__)

def extract_schema_fields(schema_str: str) -> Set[str]:
    """Extracts all property names from a JSON schema string."""
    fields = set()
    if not schema_str:
        return fields
    
    try:
        schema = json.loads(schema_str) if isinstance(schema_str, str) else schema_str
        if not isinstance(schema, dict):
            return fields
            
        def recurse(obj):
            if isinstance(obj, dict):
                if "properties" in obj and isinstance(obj["properties"], dict):
                    for k, v in obj["properties"].items():
                        fields.add(k.lower())
                        recurse(v)
                for k, v in obj.items():
                    if k != "properties":
                        recurse(v)
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item)
                    
        recurse(schema)
    except Exception as e:
        logger.warning(f"Failed to parse schema for dependency matching: {e}")
        
    return fields

def extract_required_params(params_str: str) -> Set[str]:
    fields = set()
    if not params_str:
        return fields
    try:
        params = json.loads(params_str) if isinstance(params_str, str) else params_str
        for p in params:
            if isinstance(p, dict) and "name" in p:
                fields.add(p["name"].lower())
    except Exception:
        pass
    return fields

def build_execution_dag(endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Takes a list of endpoints within a community.
    Builds a Directed Acyclic Graph (DAG) based on data dependencies.
    Returns the endpoints ordered by topological sort.
    """
    if not endpoints:
        return []
        
    if len(endpoints) == 1:
        return endpoints

    G = nx.DiGraph()
    
    # Add all endpoints as nodes
    for ep in endpoints:
        G.add_node(ep["operation_id"], data=ep)
        
    # Analyze I/O dependencies
    common_fields = {"id", "name", "description", "status", "message", "error"}
    
    for ep_a in endpoints:
        a_id = ep_a["operation_id"]
        a_method = ep_a["method"].upper()
        a_path = ep_a["url"]
        
        # What does A output?
        a_outputs = extract_schema_fields(ep_a.get("response_schema"))
        
        for ep_b in endpoints:
            b_id = ep_b["operation_id"]
            if a_id == b_id:
                continue
                
            b_method = ep_b["method"].upper()
            b_path = ep_b["url"]
            
            # What does B input?
            b_inputs = extract_schema_fields(ep_b.get("request_schema"))
            b_inputs.update(extract_required_params(ep_b.get("required_params")))
            
            edge_weight = 0
            
            # Rule 1: Schema Intersection
            # If A outputs a specific field that B requires (ignoring generic words)
            intersection = (a_outputs & b_inputs) - common_fields
            if intersection:
                edge_weight += len(intersection)
                
            # Rule 2: Path Hierarchy (RESTful dependency)
            # e.g., A = /v1/Chassis, B = /v1/Chassis/{Id}
            if a_path in b_path and len(a_path) < len(b_path):
                # A is parent of B
                # So GET / POST on parent must precede PATCH / DELETE on child
                edge_weight += 2
                
            # Rule 3: CRUD Semantics on the exact same path
            if a_path == b_path:
                crud_order = {"POST": 1, "GET": 2, "PUT": 3, "PATCH": 4, "DELETE": 5}
                a_order = crud_order.get(a_method, 99)
                b_order = crud_order.get(b_method, 99)
                if a_order < b_order:
                    edge_weight += 1
            
            # If A produces data for B, or A must logically precede B
            if edge_weight > 0:
                # To prevent cycles, only add if it doesn't create a cycle
                if not nx.has_path(G, b_id, a_id):
                    G.add_edge(a_id, b_id, weight=edge_weight)

    # Topological Sort
    try:
        # lexicographical_topological_sort guarantees deterministic order for independent nodes
        sorted_ids = list(nx.lexicographical_topological_sort(G))
    except nx.NetworkXUnfeasible:
        # Fallback if cycle somehow bypassed (shouldn't happen with has_path check)
        logger.warning("Cycle detected in community DAG, falling back to basic sort.")
        sorted_ids = [ep["operation_id"] for ep in endpoints]
        
    # Map back to endpoint dicts
    ep_map = {ep["operation_id"]: ep for ep in endpoints}
    sorted_endpoints = [ep_map[op_id] for op_id in sorted_ids]
    
    return sorted_endpoints
