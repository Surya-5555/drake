"""
Dell MCP — Design-Time Graph-Based Workflow Discovery
======================================================

Ingests stripped OpenAPI spec endpoints (Contract A), constructs a NetworkX graph
representing resource relationships and parameters, clusters endpoints using
community detection, and performs semantic labeling.
"""

from __future__ import annotations

import logging
import urllib.request
from typing import Any, Dict, List, Set, Tuple

import networkx as nx

from src.core.models import ContractA
from src.ai_clustering.explain import is_explain_mode, explain_print

logger = logging.getLogger(__name__)


def build_relationship_graph(endpoints: List[Dict[str, Any]]) -> nx.Graph:
    """
    Constructs a NetworkX graph from a list of Contract A endpoints.

    Nodes represent individual OpenAPI endpoints.
    Edges are created using semantic embedding similarity (Hybrid Threshold).
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
    try:
        embeddings = service.generate_embeddings(endpoints)
        sim_matrix = service.compute_similarity_matrix(embeddings)
    except Exception as err:
        logger.warning(
            f"EmbeddingService failed (missing dependencies?): {err}. Falling back to 0.0 semantic scores."
        )
        sim_matrix = np.zeros((len(endpoints), len(endpoints)))

    num_nodes = len(endpoints)
    if num_nodes == 0:
        return G

    # Pre-tokenize URLs and Tags
    vocab = {}
    path_arrays = []
    tags_list = []
    all_tags = set()
    
    for ep in endpoints:
        # url tokenization
        parts = [p for p in ep.get("url", "").split("/") if p and p.lower() not in ("redfish", "v1", "api")]
        encoded = []
        for p in parts:
            if p not in vocab: vocab[p] = len(vocab)
            encoded.append(vocab[p])
        path_arrays.append(encoded)
        
        # tags
        tags = ep.get("tags") or []
        if isinstance(tags, str): tags = [tags]
        tags_list.append(set(tags))
        all_tags.update(tags)

    # 1. TAG SIMILARITY (Vectorized Jaccard)
    all_tags = list(all_tags)
    tag_to_idx = {t: i for i, t in enumerate(all_tags)}
    tag_matrix = np.zeros((num_nodes, len(all_tags)), dtype=bool)
    for i, tags in enumerate(tags_list):
        for t in tags:
            tag_matrix[i, tag_to_idx[t]] = True
            
    intersection = np.dot(tag_matrix.astype(int), tag_matrix.T.astype(int))
    sum_tags = tag_matrix.sum(axis=1)
    union = sum_tags[:, None] + sum_tags[None, :] - intersection
    with np.errstate(divide='ignore', invalid='ignore'):
        tag_sim_matrix = np.where(union > 0, intersection / union, 0.0)

    # 2. PATH SIMILARITY (Vectorized)
    max_len = max((len(p) for p in path_arrays), default=0)
    if max_len == 0:
        path_sim_matrix = np.ones((num_nodes, num_nodes))
    else:
        P = np.full((num_nodes, max_len), -1, dtype=int)
        for i, p in enumerate(path_arrays):
            if p:
                P[i, :len(p)] = p
                
        len_P = np.array([len(p) for p in path_arrays])
        
        # Domain match
        domain_match = np.where((P[:, 0:1] == P[None, :, 0]) & (P[:, 0:1] != -1), 0.2, 0.0)
        
        # Shared prefix computation
        match_matrix = (P[:, None, :] == P[None, :, :]) & (P[:, None, :] != -1)
        prefix_match = np.minimum.accumulate(match_matrix, axis=2)
        shared_counts = prefix_match.sum(axis=2)
        
        # Max lengths
        max_lens = np.maximum(len_P[:, None], len_P[None, :])
        
        # Base score
        with np.errstate(divide='ignore', invalid='ignore'):
            base_score = np.where(max_lens > 0, shared_counts / max_lens, 1.0)
            
        # is_prefix bool
        is_prefix_a_in_b = shared_counts == len_P[None, :]
        is_prefix_b_in_a = shared_counts == len_P[:, None]
        is_prefix = is_prefix_a_in_b | is_prefix_b_in_a
        
        # is_sibling bool
        is_same_len = len_P[:, None] == len_P[None, :]
        is_sibling = (len_P[:, None] > 1) & is_same_len & (shared_counts == len_P[:, None] - 1)
        
        # Applying max thresholds
        mask_prefix = is_prefix & (shared_counts >= 1)
        base_score = np.where(mask_prefix, np.maximum(base_score, 0.8), base_score)
        
        mask_sibling = is_sibling & (shared_counts >= 1)
        base_score = np.where(mask_sibling & ~mask_prefix, np.maximum(base_score, 0.65), base_score)
        
        path_sim_matrix = np.clip(base_score + domain_match, 0.0, 1.0)
        
        # Handle cases where len_a == 0 or len_b == 0
        zero_len_mask = (len_P[:, None] == 0) | (len_P[None, :] == 0)
        path_sim_matrix = np.where(zero_len_mask, 0.0, path_sim_matrix)
        both_zero_mask = (len_P[:, None] == 0) & (len_P[None, :] == 0)
        path_sim_matrix = np.where(both_zero_mask, 1.0, path_sim_matrix)

    # 3. Final weighting
    final_weights = (sim_matrix * 0.25) + (tag_sim_matrix * 0.25) + (path_sim_matrix * 0.50)

    # Extract upper triangle scores for Thresholding
    triu_idx = np.triu_indices(num_nodes, k=1)
    all_scores = final_weights[triu_idx]

    # Phase 4 - Automatic Threshold Discovery
    if len(all_scores) > 0:
        p75 = np.percentile(all_scores, 75)
        p80 = np.percentile(all_scores, 80)
        p85 = np.percentile(all_scores, 85)
        p90 = np.percentile(all_scores, 90)
        p95 = np.percentile(all_scores, 95)
        
        # We mathematically clamp the similarity threshold between [0.71, 0.72] to guarantee 
        # the optimal "Goldilocks Zone" for LLM context window limits and tool precision in production.
        if num_nodes >= 50:
            threshold = max(0.71, min(0.72, p90))
        else:
            threshold = max(0.50, min(0.70, p90))
    else:
        threshold = 0.50
        p75 = p80 = p85 = p90 = p95 = 0.0
        
    G.graph["threshold"] = threshold

    if is_explain_mode() and all_scores:
        content_thresh = (
            f"Mean: {np.mean(all_scores):.3f}\n"
            f"Median: {np.median(all_scores):.3f}\n"
            f"p75: {p75:.3f}\n"
            f"p80: {p80:.3f}\n"
            f"p85: {p85:.3f}\n"
            f"p90: {p90:.3f}\n"
            f"p95: {p95:.3f}\n\n"
            f"Selected Threshold: {threshold:.3f}"
        )
        explain_print("AUTOMATIC THRESHOLD DISCOVERY", content_thresh)

    # Phase 2 - Add edges and track diagnostics
    accepted_edges = 0
    rejected_edges = 0
    
    # We create the candidate edges for accepted entries
    # using np.where
    accepted_mask = final_weights > threshold
    np.fill_diagonal(accepted_mask, False)
    # Only upper triangle to avoid duplicate edges
    accepted_mask = accepted_mask & np.triu(np.ones((num_nodes, num_nodes), dtype=bool), k=1)
    
    accepted_indices = np.argwhere(accepted_mask)
    
    top_edges = []
    acc_sem, acc_path, acc_tag = [], [], []
    
    for idx in accepted_indices:
        i, j = idx
        w = float(final_weights[i, j])
        s_score = float(sim_matrix[i, j])
        p_score = float(path_sim_matrix[i, j])
        t_score = float(tag_sim_matrix[i, j])
        
        top_edges.append((i, j, w, s_score, p_score, t_score))
        
        op_id_i = endpoints[i]["operation_id"]
        op_id_j = endpoints[j]["operation_id"]
        G.add_edge(op_id_i, op_id_j, weight=w)
        
        accepted_edges += 1
        acc_sem.append(s_score)
        acc_path.append(p_score)
        acc_tag.append(t_score)
        
    top_edges = sorted(top_edges, key=lambda x: x[2], reverse=True)
    rejected_edges = len(all_scores) - accepted_edges

    if is_explain_mode():
        total_comparisons = len(all_scores)
        acceptance_rate = accepted_edges / total_comparisons if total_comparisons > 0 else 0
        
        if len(all_scores) > 0:
            hist, bins = np.histogram(all_scores, bins=10, range=(0.0, 1.0))
            hist_str = "\n".join(f"{bins[k]:.1f}-{bins[k+1]:.1f}: {hist[k]}" for k in range(10))
        else:
            hist_str = "No data"
        
        top_100_str = "\n".join(
            f"{endpoints[u]['operation_id']} <-> {endpoints[v]['operation_id']} (Score: {w:.3f})"
            for u, v, w, _, _, _ in top_edges[:100]
        )
        
        avg_s = np.mean(acc_sem) if acc_sem else 0
        avg_p = np.mean(acc_path) if acc_path else 0
        avg_t = np.mean(acc_tag) if acc_tag else 0
        
        content_graph = (
            f"Total endpoints: {num_nodes}\n"
            f"Total candidate comparisons: {total_comparisons}\n"
            f"Accepted edges: {accepted_edges}\n"
            f"Rejected edges: {rejected_edges}\n"
            f"Edge acceptance rate: {acceptance_rate:.2%}\n\n"
            f"Average semantic score (accepted): {avg_s:.3f}\n"
            f"Average path score (accepted): {avg_p:.3f}\n"
            f"Average tag score (accepted): {avg_t:.3f}\n\n"
            f"Score distribution histogram:\n{hist_str}\n\n"
            f"Top 100 strongest relationships:\n{top_100_str}"
        )
        explain_print("GRAPH VALIDATION", content_graph)

    return G


def detect_communities(G: nx.Graph) -> List[Set[str]]:
    """
    Groups endpoints into community clusters using Leiden community detection.
    Falls back to single-node communities if no edges are present.
    """
    if G.number_of_edges() == 0:
        return [{node} for node in G.nodes()]

    try:
        import igraph as ig
        import leidenalg

        nodes = list(G.nodes())
        node_indices = {n: i for i, n in enumerate(nodes)}

        edges = [(node_indices[u], node_indices[v]) for u, v in G.edges()]
        weights = [data.get("weight", 1.0) for u, v, data in G.edges(data=True)]

        g_ig = ig.Graph(n=len(nodes), edges=edges, directed=False)
        g_ig.es["weight"] = weights

        partition = leidenalg.find_partition(
            g_ig,
            leidenalg.ModularityVertexPartition,
            weights="weight",
            n_iterations=-1,
            seed=42,
        )

        communities = []
        for comm in partition:
            communities.append(set(nodes[i] for i in comm))

        return communities
    except ImportError as err:
        logger.error(f"Failed to import igraph/leidenalg: {err}. Please install dependencies.")
        return [{node} for node in G.nodes()]


def check_ollama_status() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.0)
        return True
    except Exception:
        return False


def generate_semantic_label(
    workflow_id: str,
    endpoints: List[Dict[str, Any]],
    use_llm: bool = True,
) -> Tuple[str, str, str, float]:
    from src.ai_clustering.workflow_naming import generate_system_name
    
    # Deterministic naming (Phase 6 occurs inside generate_system_name now)
    system_name = generate_system_name(endpoints)
    
    methods = [ep["method"] for ep in endpoints]
    has_write = any(m in ["POST", "PATCH", "PUT", "DELETE"] for m in methods)

    action = "Management" if has_write else "Observability"
    
    fallback_display_name = system_name.replace("_", " ").title()
    heuristic_desc = f"{action} layer for {fallback_display_name}. Configured with {len(endpoints)} underlying endpoints."

    if use_llm and check_ollama_status():
        try:
            # Phase 7 Fix
            from src.ai_clustering.ollama_service import OllamaService

            service = OllamaService()

            endpoint_summaries = "\n".join(
                [f"- {ep['method']} {ep['url']} ({ep['operation_id']})" for ep in endpoints]
            )

            prompt = f"""
            You are a Dell Enterprise IT Architect naming a workflow.
            The internal deterministic system name for this workflow is: {system_name}
            
            The underlying iDRAC API endpoints are:
            {endpoint_summaries}
            
            DO NOT alter membership.
            DO NOT invent endpoints.
            DO NOT suggest changes.

            You MUST return a JSON object containing a 'workflows' array with exactly one item.
            Set 'display_name' to a 2-6 word Title Case operational name.
            Set 'generated_description' to a single concise sentence describing its operational capability.
            """

            if is_explain_mode():
                explain_print("LLM VALIDATION - PROMPT SENT", prompt.strip())

            data = service.generate_workflow_mapping(prompt)

            workflows = data.get("workflows", [])
            if workflows:
                wf = workflows[0]
                if hasattr(wf, "model_dump"):
                    wf = wf.model_dump()
                elif hasattr(wf, "dict"):
                    wf = wf.dict()
                
                display_name = wf.get("display_name", fallback_display_name)
                desc = wf.get("generated_description", heuristic_desc)

                if is_explain_mode():
                    content = (
                        f"Parsed Response:\n"
                        f"display_name: {display_name}\n"
                        f"description: {desc}"
                    )
                    explain_print("LLM VALIDATION - PARSED RESPONSE", content)

                return system_name, display_name, desc, 0.95
        except Exception as err:
            logger.warning(f"Ollama labeling failed: {err}. Falling back to heuristics.")
            if is_explain_mode():
                explain_print("LLM VALIDATION - FALLBACK", f"Reason: {err}")

    return system_name, fallback_display_name, heuristic_desc, 0.85


def run_pipeline(contract_a_data: ContractA) -> None:
    import hashlib
    import numpy as np
    from src.core.database import (
        log_audit_event,
        save_endpoints,
        save_workflows,
        save_edges,
    )

    log_audit_event(
        "pipeline_started",
        "pending",
        "Ingestion and graph clustering pipeline triggered.",
    )

    endpoints = []
    for ep in contract_a_data.endpoints:
        endpoints.append(
            {
                "operation_id": ep.operation_id,
                "method": ep.method,
                "url": ep.url,
                "required_params": [p.name for p in ep.required_params],
                "tags": ep.tags,
                "summary": ep.summary,
                "description": ep.description,
                "request_schema": ep.request_schema,
                "response_schema": ep.response_schema,
            }
        )

    save_endpoints(endpoints)

    G = build_relationship_graph(endpoints)

    edges_list = []
    for u, v, data in G.edges(data=True):
        edges_list.append({"source": u, "target": v, "weight": data.get("weight", 1.0)})
    save_edges(edges_list)

    communities = detect_communities(G)

    if is_explain_mode():
        threshold = G.graph.get("threshold", 0.50)
        
        for idx, comm_node_ids in enumerate(communities, 1):
            comm_id = f"c_{idx:03d}"
            members = []
            
            # Phase 5 Metrics
            comm_size = len(comm_node_ids)
            internal_sims = []
            if comm_size > 1:
                # Calculate internal similarity
                for u in comm_node_ids:
                    for v in comm_node_ids:
                        if u != v and G.has_edge(u, v):
                            internal_sims.append(G[u][v]["weight"])
            
            avg_sim = np.mean(internal_sims) if internal_sims else 0.0
            min_sim = np.min(internal_sims) if internal_sims else 0.0
            max_sim = np.max(internal_sims) if internal_sims else 0.0
            cohesion = avg_sim * (comm_size / (comm_size + 1)) if comm_size > 1 else 0.0
            
            warnings = []
            if comm_size == 1:
                warnings.append("Suspicious: Size = 1")
            elif cohesion < threshold:
                warnings.append(f"Suspicious: Low cohesion ({cohesion:.3f} < {threshold:.3f})")
                
            for n_idx, op_id in enumerate(comm_node_ids, 1):
                ep = next(e for e in endpoints if e["operation_id"] == op_id)
                members.append(f"{n_idx}. {ep['method']} {ep.get('url', '')}")
            members_str = "\n".join(members)
            
            content = (
                f"Community ID: {comm_id}\n"
                f"Size: {comm_size}\n"
                f"Average Internal Similarity: {avg_sim:.3f}\n"
                f"Min Similarity: {min_sim:.3f}\n"
                f"Max Similarity: {max_sim:.3f}\n"
                f"Cohesion Score: {cohesion:.3f}\n"
                f"Flags: {', '.join(warnings) if warnings else 'None'}\n\n"
                f"Endpoints:\n{members_str}"
            )
            explain_print("COMMUNITY VALIDATION", content)

    # Build a lookup dict so every endpoint gets its community_id assigned exactly once
    ep_by_op_id = {ep["operation_id"]: ep for ep in endpoints}
    workflows_list = []

    for comm in communities:
        sorted_ops = sorted(list(comm))
        comm_hash = hashlib.md5("".join(sorted_ops).encode("utf-8")).hexdigest()[:8]
        comm_id = f"c_{comm_hash}"

        comm_endpoints = []
        for op_id in sorted_ops:
            ep = ep_by_op_id.get(op_id)
            if ep is not None:
                ep["community_id"] = comm_id
                comm_endpoints.append(ep)

        workflow_id = f"wf_{comm_id}"
        system_name, display_name, wf_desc, confidence = generate_semantic_label(
            workflow_id, comm_endpoints, use_llm=False
        )

        methods = [ep["method"] for ep in comm_endpoints]
        if "DELETE" in methods:
            risk = "critical"
        elif "POST" in methods:
            risk = "high"
        elif "PATCH" in methods or "PUT" in methods:
            risk = "medium"
        else:
            risk = "low"

        workflows_list.append(
            {
                "id": workflow_id,
                "system_name": system_name,
                "display_name": display_name,
                "risk_level": risk,
                "cluster_size": len(comm_endpoints),
                "confidence": confidence,
                "generated_description": wf_desc,
                "community_id": comm_id,
            }
        )

    # Save ALL endpoints (community_id now set for every one)
    updated_endpoints = list(ep_by_op_id.values())
    save_endpoints(updated_endpoints)
    save_workflows(workflows_list)
    log_audit_event(
        "workflow_generated",
        "success",
        f"Graph construction completed. Clustered {len(endpoints)} endpoints into {len(workflows_list)} workflow tools.",
    )
    
    return {
        "embeddings_generated": len(endpoints),
        "graph_nodes": G.number_of_nodes(),
        "graph_edges": G.number_of_edges(),
        "communities": len(communities),
        "workflow_names": len(workflows_list),
        "llm_labels": len([w for w in workflows_list if w["confidence"] >= 0.9]),
        "workflows_saved": len(workflows_list)
    }
