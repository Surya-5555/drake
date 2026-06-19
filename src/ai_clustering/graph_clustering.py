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
    Edges are created using semantic embedding similarity (Hybrid Threshold + Top-K).
    """
    from src.ai_clustering.embedding_service import EmbeddingService
    import numpy as np

    G = nx.Graph()

    if not endpoints:
        return G

    # Add all endpoints as nodes
    for ep in endpoints:
        G.add_node(ep["operation_id"], **ep)

    service = EmbeddingService()
    embeddings = service.generate_embeddings(endpoints)
    sim_matrix = service.compute_similarity_matrix(embeddings)

    def compute_path_similarity(url_a: str, url_b: str) -> float:
        parts_a = [p for p in url_a.split("/") if p]
        parts_b = [p for p in url_b.split("/") if p]
        if not parts_a and not parts_b:
            return 1.0
        if not parts_a or not parts_b:
            return 0.0
        shared = 0
        for a, b in zip(parts_a, parts_b):
            if a == b:
                shared += 1
            else:
                break
        return float(shared) / max(len(parts_a), len(parts_b))

    def compute_tag_similarity(tags_a: List[str], tags_b: List[str]) -> float:
        set_a = set(tags_a)
        set_b = set(tags_b)
        if not set_a or not set_b:
            return 0.0
        union = len(set_a.union(set_b))
        return float(len(set_a.intersection(set_b))) / union if union > 0 else 0.0

    # Hybrid Threshold + Top-K for edges
    # For each node, find the top 10 most similar nodes (excluding self) with similarity > 0.50
    k = 10
    threshold = 0.50
    num_nodes = len(endpoints)

    for i in range(num_nodes):
        op_id_i = endpoints[i]["operation_id"]
        tags_i = endpoints[i].get("tags", [])
        if isinstance(tags_i, str):
            tags_i = [tags_i]
        url_i = endpoints[i].get("url", "")
        
        final_weights = np.zeros(num_nodes)
        
        for j in range(num_nodes):
            if i == j:
                final_weights[j] = 0.0
                continue
                
            semantic_score = float(sim_matrix[i][j])
            
            tags_j = endpoints[j].get("tags", [])
            if isinstance(tags_j, str):
                tags_j = [tags_j]
            tag_score = compute_tag_similarity(tags_i, tags_j)
            
            url_j = endpoints[j].get("url", "")
            path_score = compute_path_similarity(url_i, url_j)
            
            final_weight = (semantic_score * 0.6) + (tag_score * 0.25) + (path_score * 0.15)
            final_weights[j] = final_weight
            
        # Get indices of top k elements
        if num_nodes - 1 < k:
            top_k_indices = np.argsort(final_weights)[::-1]
        else:
            top_k_indices = np.argpartition(final_weights, -k)[-k:]
            # Sort the top k indices
            top_k_indices = top_k_indices[np.argsort(final_weights[top_k_indices])][::-1]

        for j in top_k_indices:
            weight = final_weights[j]
            if weight > threshold:
                op_id_j = endpoints[j]["operation_id"]
                # networkx Graph is undirected, so adding (i, j) or (j, i) is the same.
                if not G.has_edge(op_id_i, op_id_j):
                    G.add_edge(op_id_i, op_id_j, weight=float(weight))
                else:
                    # Keep the max weight if there's asymmetry
                    G[op_id_i][op_id_j]["weight"] = max(G[op_id_i][op_id_j]["weight"], float(weight))

    return G


def detect_communities(G: nx.Graph) -> List[Set[str]]:
    """
    Groups endpoints into community clusters using Leiden community detection.
    Falls back to single-node communities if no edges are present.
    """
    # Check if we have edges to cluster
    if G.number_of_edges() == 0:
        return [{node} for node in G.nodes()]

    try:
        import igraph as ig
        import leidenalg
        
        # Convert NetworkX to igraph
        nodes = list(G.nodes())
        node_indices = {n: i for i, n in enumerate(nodes)}
        
        edges = [(node_indices[u], node_indices[v]) for u, v in G.edges()]
        weights = [data.get('weight', 1.0) for u, v, data in G.edges(data=True)]
        
        g_ig = ig.Graph(n=len(nodes), edges=edges, directed=False)
        g_ig.es['weight'] = weights
        
        # Run Leiden algorithm
        partition = leidenalg.find_partition(
            g_ig, 
            leidenalg.ModularityVertexPartition,
            weights='weight',
            n_iterations=-1,
            seed=42 # for determinism
        )
        
        # Map back to original node IDs
        communities = []
        for comm in partition:
            communities.append(set(nodes[i] for i in comm))
            
        return communities
    except ImportError as err:
        logger.error(f"Failed to import igraph/leidenalg: {err}. Please install dependencies.")
        # Fallback to single node communities if ML packages are missing
        return [{node} for node in G.nodes()]


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
            from ai_cluster.services.ollama_service import OllamaService
            service = OllamaService()
            
            endpoint_summaries = "\n".join(
                [f"- {ep['method']} {ep['url']} ({ep['operation_id']})" for ep in endpoints]
            )
            op_ids = [ep['operation_id'] for ep in endpoints]
            
            prompt = f"""
            You are a Dell Enterprise IT Architect.
            Create a single workflow that groups these iDRAC API endpoints:
            {endpoint_summaries}
            
            You MUST return a JSON object containing a 'workflows' array with exactly one item.
            Set 'workflow_name' to a descriptive snake_case identifier.
            Set 'underlying_api_calls' to exactly these operation IDs: {op_ids}
            Set 'reasoning' to a single-item array containing a clear business description (maximum 2 sentences).
            """
            
            data = service.generate_workflow_mapping(prompt)
            
            workflows = data.get("workflows", [])
            if workflows:
                wf = workflows[0]
                name = wf.get("workflow_name", heuristic_name)
                reasoning = wf.get("reasoning", [])
                desc = reasoning[0] if reasoning else heuristic_desc
                
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
      2. Construct NetworkX graph using Semantic Embeddings.
      3. Cluster endpoints using Leiden algorithm.
      4. Generate deterministic community IDs.
      5. Semantically label communities.
      6. Write edges and workflows to SQLite.
    """
    import hashlib
    from src.core.database import log_audit_event, save_endpoints, save_workflows, save_edges
    
    log_audit_event("pipeline_started", "pending", "Ingestion and graph clustering pipeline triggered.")
    
    endpoints = []
    for ep in contract_a_data.endpoints:
        endpoints.append({
            "operation_id": ep.operation_id,
            "method": ep.method,
            "url": ep.url,
            "required_params": [p.name for p in ep.required_params],
            "tags": ep.tags,
            "summary": ep.summary,
            "description": ep.description,
            "request_schema": ep.request_schema,
            "response_schema": ep.response_schema,
        })

    # Save to database initially
    save_endpoints(endpoints)

    # Build Graph
    G = build_relationship_graph(endpoints)
    
    # Extract edges to save
    edges_list = []
    for u, v, data in G.edges(data=True):
        edges_list.append({
            "source": u,
            "target": v,
            "weight": data.get("weight", 1.0)
        })
    save_edges(edges_list)
    
    # Detect communities
    communities = detect_communities(G)
    
    # Update endpoints in DB with deterministic MD5 community IDs
    updated_endpoints = []
    workflows_list = []
    
    for comm in communities:
        # Sort operation_ids to ensure deterministic hashing
        sorted_ops = sorted(list(comm))
        comm_hash = hashlib.md5("".join(sorted_ops).encode('utf-8')).hexdigest()[:8]
        comm_id = f"c_{comm_hash}"
        
        comm_endpoints = []
        for op_id in sorted_ops:
            for ep in endpoints:
                if ep["operation_id"] == op_id:
                    ep["community_id"] = comm_id
                    updated_endpoints.append(ep)
                    comm_endpoints.append(ep)
                    break
                    
        # Discover and label workflows
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

    save_endpoints(updated_endpoints)
    save_workflows(workflows_list)
    log_audit_event(
        "workflow_generated",
        "success",
        f"Graph construction completed. Clustered {len(endpoints)} endpoints into {len(workflows_list)} workflow tools."
    )
