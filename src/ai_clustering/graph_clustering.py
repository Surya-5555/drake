"""
Dell MCP — Design-Time Graph-Based Workflow Discovery
======================================================

Ingests stripped OpenAPI spec endpoints (Contract A), constructs a NetworkX graph
representing resource relationships and parameters, clusters endpoints using
community detection, and performs semantic labeling.
"""

from __future__ import annotations

import logging
import os
import re
import urllib.request
from typing import Any, Dict, List, Set, Tuple

import networkx as nx
import ollama

from src.core.database import log_audit_event, save_endpoints, save_workflows
from src.core.models import ContractA

logger = logging.getLogger(__name__)


def build_relationship_graph(endpoints: List[Dict[str, Any]]) -> nx.Graph:
    """
    Constructs a NetworkX graph from a list of Contract A endpoints.
    
    Nodes represent individual OpenAPI endpoints.
    Edges are created and weighted based on shared base paths, parameters, and resources.
    """
    G = nx.Graph()

    # Add all endpoints as nodes
    for ep in endpoints:
        G.add_node(ep["operation_id"], **ep)

    # Compile list of nodes
    nodes = list(G.nodes(data=True))

    def get_base_path(path: str) -> str:
        """Extract the first 3 segments of a path to group by resource prefix."""
        parts = [p for p in path.split("/") if p and not p.startswith("{")]
        return "/" + "/".join(parts[:3])

    # Connect nodes based on relationship heuristics
    for i in range(len(nodes)):
        id_i, data_i = nodes[i]
        path_i = data_i["url"]
        base_i = get_base_path(path_i)
        params_i = set(data_i["required_params"])

        for j in range(i + 1, len(nodes)):
            id_j, data_j = nodes[j]
            path_j = data_j["url"]
            base_j = get_base_path(path_j)
            params_j = set(data_j["required_params"])

            weight = 0.0

            # 1. Share exact base resource path
            if base_i == base_j and base_i != "/":
                weight += 4.0

            # 2. Share path parameter signatures
            shared_params = params_i.intersection(params_j)
            if shared_params:
                weight += len(shared_params) * 1.5

            # 3. Method dependency (e.g. GET and PATCH on same path)
            if path_i == path_j:
                weight += 5.0

            # If they have a relationship, add the edge
            if weight > 0:
                G.add_edge(id_i, id_j, weight=weight)

    return G


def detect_communities(G: nx.Graph) -> List[Set[str]]:
    """
    Groups endpoints into community clusters using NetworkX community detection.
    Falls back to single-node communities if no edges are present.
    """
    # Check if we have edges to cluster
    if G.number_of_edges() == 0:
        return [{node} for node in G.nodes()]

    try:
        from networkx.algorithms.community import label_propagation_communities
        communities = list(label_propagation_communities(G))
    except Exception as err:
        logger.warning(f"Label propagation failed: {err}. Using modularity optimization.")
        from networkx.algorithms.community import greedy_modularity_communities
        communities = [set(c) for c in greedy_modularity_communities(G)]

    return communities


def check_ollama_status() -> bool:
    """Checks if Ollama daemon is reachable on localhost:11434."""
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.0)
        return True
    except Exception:
        return False


def generate_semantic_label(
    workflow_id: str,
    endpoints: List[Dict[str, Any]],
    use_llm: bool = True,
) -> Tuple[str, str, float]:
    """
    Assigns a user-friendly workflow name and description to a cluster.
    If Ollama/Llama3 is available, requests semantic summary. Otherwise,
    falls back to a high-fidelity path-based heuristic model.
    """
    # 1. Gather paths and methods
    methods = [ep["method"] for ep in endpoints]
    paths = [ep["url"] for ep in endpoints]
    
    # 2. Heuristic extraction
    # Determine base domain segment
    segments = []
    for path in paths:
        parts = [p for p in path.split("/") if p and not p.startswith("{")]
        if len(parts) >= 2:
            segments.append(parts[1])
        elif len(parts) == 1:
            segments.append(parts[0])
            
    primary_domain = max(set(segments), key=segments.count) if segments else "system"
    
    # Check if destructive actions exist (POST, PATCH, DELETE)
    has_write = any(m in ["POST", "PATCH", "PUT", "DELETE"] for m in methods)
    
    # Formulate heuristic label
    tone = "workflow"
    action = "Management" if has_write else "Observability"
    
    # Map raw domains to enterprise descriptions
    domain_mappings = {
        "Systems": ("Server Hardware", "Query hardware logs, power states, and server metrics."),
        "Chassis": ("Chassis Controller", "Monitor power supplies, fan controls, and thermal levels."),
        "UpdateService": ("Firmware Update", "Stage firmware updates and inspect update service inventory."),
        "AccountService": ("User Account", "Configure and secure user directories, privileges, and accounts."),
        "SessionService": ("API Authentication", "Manage sessions, active logins, and web service keys."),
        "Managers": ("iDRAC BMC", "Access Baseboard Management Controller properties and network configurations."),
    }

    friendly_name, default_desc = domain_mappings.get(
        primary_domain, (primary_domain.capitalize(), f"Integrates {primary_domain} REST operations.")
    )
    
    heuristic_name = f"{primary_domain.lower()}_{'update' if has_write else 'query'}_workflow"
    heuristic_desc = f"{action} layer for {friendly_name}. {default_desc} Configured with {len(endpoints)} underlying endpoints."

    # 3. LLM semantic labeling (if requested and online)
    if use_llm and check_ollama_status():
        try:
            client = ollama.Client()
            endpoint_summaries = "\n".join(
                [f"- {ep['method']} {ep['url']} ({ep['operation_id']})" for ep in endpoints]
            )
            
            prompt = f"""
            You are a Dell Enterprise IT Architect.
            Name and describe an automation workflow that clusters these iDRAC API endpoints:
            {endpoint_summaries}
            
            Format response as JSON with keys:
            - workflow_name: snake_case identifier (e.g. system_inventory_workflow)
            - generated_description: clear business description (maximum 2 sentences)
            
            Do not include explanations or markdown outside JSON.
            """
            
            response = client.chat(
                model="llama3",
                messages=[{"role": "user", "content": prompt}],
                format={"type": "object", "properties": {"workflow_name": {"type": "string"}, "generated_description": {"type": "string"}}, "required": ["workflow_name", "generated_description"]},
                options={"temperature": 0.0}
            )
            
            import json
            data = json.loads(response["message"]["content"])
            name = data.get("workflow_name", heuristic_name)
            desc = data.get("generated_description", heuristic_desc)
            
            # Enforce snake_case for workflow name
            if not re.match(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$", name):
                name = heuristic_name
                
            return name, desc, 0.95
        except Exception as err:
            logger.warning(f"Ollama labeling failed: {err}. Falling back to heuristics.")

    return heuristic_name, heuristic_desc, 0.85


def run_pipeline(contract_a_data: ContractA) -> None:
    """
    Executes the compile-time discovery pipeline:
      1. Save raw endpoints to SQLite.
      2. Construct NetworkX graph.
      3. Cluster endpoints into communities.
      4. Semantically label communities.
      5. Write discovered workflows to SQLite.
    """
    log_audit_event("pipeline_started", "pending", "Ingestion and graph clustering pipeline triggered.")
    
    endpoints = []
    for ep in contract_a_data.endpoints:
        endpoints.append({
            "operation_id": ep.operation_id,
            "method": ep.method,
            "url": ep.url,
            "required_params": [p.name for p in ep.required_params],
        })

    # Save to database
    save_endpoints(endpoints)

    # Build Graph
    G = build_relationship_graph(endpoints)
    
    # Detect communities
    communities = detect_communities(G)
    
    # Update endpoints in DB with community IDs
    updated_endpoints = []
    for idx, comm in enumerate(communities):
        comm_id = str(idx + 1)
        for op_id in comm:
            for ep in endpoints:
                if ep["operation_id"] == op_id:
                    ep["community_id"] = comm_id
                    updated_endpoints.append(ep)
                    
    save_endpoints(updated_endpoints)

    # Discover and label workflows
    workflows_list = []
    for idx, comm in enumerate(communities):
        comm_id = str(idx + 1)
        comm_endpoints = [ep for ep in updated_endpoints if ep["community_id"] == comm_id]
        
        workflow_id = f"wf_{comm_id}"
        wf_name, wf_desc, confidence = generate_semantic_label(workflow_id, comm_endpoints)
        
        # Calculate risk based on destructive verbs
        methods = [ep["method"] for ep in comm_endpoints]
        if "DELETE" in methods:
            risk = "critical"
        elif "POST" in methods:
            risk = "high"
        elif "PATCH" in methods or "PUT" in methods:
            risk = "medium"
        else:
            risk = "low"

        workflows_list.append({
            "id": workflow_id,
            "workflow_name": wf_name,
            "risk_level": risk,
            "cluster_size": len(comm_endpoints),
            "confidence": confidence,
            "generated_description": wf_desc,
            "community_id": comm_id,
        })

    save_workflows(workflows_list)
    log_audit_event(
        "workflow_generated",
        "success",
        f"Graph construction completed. Clustered {len(endpoints)} endpoints into {len(workflows_list)} workflow tools."
    )
