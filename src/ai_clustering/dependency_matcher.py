import json
import logging
import networkx as nx
from typing import List, Dict, Any, Set

logger = logging.getLogger(__name__)

def extract_schema_fields_typed(schema_str: Any) -> Dict[str, str]:
    """Extracts property names and types from a JSON schema string recursively."""
    fields = {}
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
                        t = v.get("type", "string") if isinstance(v, dict) else "unknown"
                        fields[k] = t
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

def extract_required_params_typed(params_str: Any) -> Dict[str, str]:
    fields = {}
    if not params_str:
        return fields
    try:
        params = json.loads(params_str) if isinstance(params_str, str) else params_str
        for p in params:
            if isinstance(p, dict) and "name" in p:
                t = p.get("schema", {}).get("type", "string")
                fields[p["name"]] = t
    except Exception:
        pass
    return fields

def build_execution_dag(endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Takes a list of endpoints within a community.
    Builds a Directed Acyclic Graph (DAG) based on data dependencies.
    Resolves Cycles automatically.
    Returns the endpoints ordered by topological sort with variable_bindings injected.
    """
    if not endpoints:
        return []
    if len(endpoints) == 1:
        endpoints[0]["variable_bindings"] = json.dumps({})
        return endpoints

    G = nx.DiGraph()
    bindings = {ep["operation_id"]: {} for ep in endpoints}
    
    for ep in endpoints:
        G.add_node(ep["operation_id"], data=ep)
        
    common_fields = {"id", "name", "description", "status", "message", "error", "type"}
    
    for ep_a in endpoints:
        a_id = ep_a["operation_id"]
        a_method = ep_a["method"].upper()
        a_path = ep_a["url"]
        a_outputs = extract_schema_fields_typed(ep_a.get("response_schema"))
        
        for ep_b in endpoints:
            b_id = ep_b["operation_id"]
            if a_id == b_id:
                continue
            b_method = ep_b["method"].upper()
            b_path = ep_b["url"]
            b_inputs = extract_schema_fields_typed(ep_b.get("request_schema"))
            b_inputs.update(extract_required_params_typed(ep_b.get("required_params")))
            
            edge_weight = 0
            mapped_fields = []
            
            # Rule 1: Type-Aware Schema Intersection
            for a_key, a_type in a_outputs.items():
                if a_key.lower() in common_fields:
                    continue
                for b_key, b_type in b_inputs.items():
                    if a_key.lower() == b_key.lower() and a_type == b_type:
                        edge_weight += 5
                        mapped_fields.append((b_key, a_key))
            
            # Rule 2: Path Hierarchy (RESTful dependency)
            if a_path in b_path and len(a_path) < len(b_path):
                edge_weight += 10
                
            # Rule 3: CRUD Semantics on the exact same path
            if a_path == b_path:
                crud_order = {"POST": 1, "GET": 2, "PUT": 3, "PATCH": 4, "DELETE": 5}
                a_order = crud_order.get(a_method, 99)
                b_order = crud_order.get(b_method, 99)
                if a_order < b_order:
                    edge_weight += 3
            
            if edge_weight > 0:
                G.add_edge(a_id, b_id, weight=edge_weight)
                for b_key, a_key in mapped_fields:
                    if b_key not in bindings[b_id]:
                        bindings[b_id][b_key] = f"{{{{{a_id}.{a_key}}}}}"

    # Cycle Management Engine
    try:
        sorted_ids = list(nx.lexicographical_topological_sort(G))
    except nx.NetworkXUnfeasible:
        logger.warning("Cycle detected in DAG. Initializing Cycle Management Engine.")
        while True:
            try:
                cycles = list(nx.simple_cycles(G))
                if not cycles:
                    break
                for cycle in cycles:
                    min_weight = float('inf')
                    weakest_edge = None
                    for i in range(len(cycle)):
                        u = cycle[i]
                        v = cycle[(i + 1) % len(cycle)]
                        if G.has_edge(u, v):
                            w = G[u][v]["weight"]
                            if w < min_weight:
                                min_weight = w
                                weakest_edge = (u, v)
                    if weakest_edge:
                        G.remove_edge(*weakest_edge)
                        logger.info(f"Cycle Management: Removed weakest edge {weakest_edge} (weight {min_weight})")
                        # Also remove the binding that caused this edge
                        target_id = weakest_edge[1]
                        bindings[target_id] = {k: v for k, v in bindings[target_id].items() if not v.startswith(f"{{{{{weakest_edge[0]}.")}
                sorted_ids = list(nx.lexicographical_topological_sort(G))
                break
            except nx.NetworkXUnfeasible:
                continue

    ep_map = {ep["operation_id"]: ep for ep in endpoints}
    sorted_endpoints = []
    
    # Handle disconnected nodes gracefully
    all_nodes = set(ep_map.keys())
    sorted_set = set(sorted_ids)
    missing = all_nodes - sorted_set
    
    for op_id in sorted_ids + list(missing):
        ep = ep_map[op_id]
        ep["variable_bindings"] = json.dumps(bindings.get(op_id, {}))
        sorted_endpoints.append(ep)
        
    return sorted_endpoints
