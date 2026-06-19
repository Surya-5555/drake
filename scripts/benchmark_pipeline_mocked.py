import time
import hashlib
import numpy as np
import networkx as nx
from pathlib import Path
from src.parser.openapi_parser import OpenAPIParser
from src.ai_clustering.graph_clustering import detect_communities
from src.core.database import save_endpoints, save_workflows, save_edges


def benchmark():
    print("Starting Fast Validation Benchmark (Mocked Embeddings)...", flush=True)
    timings = {}
    total_start = time.perf_counter()

    root_dir = Path(__file__).resolve().parent.parent
    sample_file = root_dir / "data" / "openapi_sample.json"

    # 1. Parse Time
    t0 = time.perf_counter()
    parser = OpenAPIParser(sample_file)
    contract_a = parser.parse_and_flatten()
    t1 = time.perf_counter()
    timings["Parsing"] = t1 - t0

    endpoints = []
    for ep in contract_a.endpoints:
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

    # 2. Embedding Generation (MOCKED)
    t0 = time.perf_counter()
    # Mock embeddings: (N, 384) random vectors
    embeddings = np.random.rand(len(endpoints), 384)
    # Normalize
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms
    t1 = time.perf_counter()
    timings["Embedding Generation"] = t1 - t0

    # 3. Similarity Matrix
    t0 = time.perf_counter()
    # Cosine similarity is dot product for normalized vectors
    sim_matrix = np.dot(embeddings, embeddings.T)
    t1 = time.perf_counter()
    timings["Similarity Matrix"] = t1 - t0

    # 4. Graph Construction
    t0 = time.perf_counter()
    G = nx.Graph()
    for ep in endpoints:
        G.add_node(ep["operation_id"], **ep)

    k = 10
    threshold = 0.50
    num_nodes = len(endpoints)

    for i in range(num_nodes):
        op_id_i = endpoints[i]["operation_id"]
        sims = sim_matrix[i].copy()
        sims[i] = 0.0

        if num_nodes - 1 < k:
            top_k_indices = np.argsort(sims)[::-1]
        else:
            top_k_indices = np.argpartition(sims, -k)[-k:]
            top_k_indices = top_k_indices[np.argsort(sims[top_k_indices])][::-1]

        for j in top_k_indices:
            weight = sims[j]
            if weight > threshold:
                op_id_j = endpoints[j]["operation_id"]
                if not G.has_edge(op_id_i, op_id_j):
                    G.add_edge(op_id_i, op_id_j, weight=float(weight))
                else:
                    G[op_id_i][op_id_j]["weight"] = max(
                        G[op_id_i][op_id_j]["weight"], float(weight)
                    )

    edges_list = [
        {"source": u, "target": v, "weight": data.get("weight", 1.0)}
        for u, v, data in G.edges(data=True)
    ]
    t1 = time.perf_counter()
    timings["Graph Construction"] = t1 - t0

    # 5. Leiden Clustering
    t0 = time.perf_counter()
    communities = detect_communities(G)
    t1 = time.perf_counter()
    timings["Leiden Clustering"] = t1 - t0

    # 6. Workflow Labeling (Heuristic fallback forced)
    t0 = time.perf_counter()
    updated_endpoints = []
    workflows_list = []

    for comm in communities:
        sorted_ops = sorted(list(comm))
        comm_hash = hashlib.md5("".join(sorted_ops).encode("utf-8")).hexdigest()[:8]
        comm_id = f"c_{comm_hash}"

        comm_endpoints = []
        for op_id in sorted_ops:
            for ep in endpoints:
                if ep["operation_id"] == op_id:
                    ep["community_id"] = comm_id
                    updated_endpoints.append(ep)
                    comm_endpoints.append(ep)
                    break

        workflow_id = f"wf_{comm_id}"

        # Heuristic labeling
        methods = [ep["method"] for ep in comm_endpoints]
        tags = set()
        for ep in comm_endpoints:
            if isinstance(ep.get("tags"), list):
                tags.update(ep["tags"])
            elif isinstance(ep.get("tags"), str):
                tags.add(ep["tags"])

        primary_tag = sorted(list(tags))[0] if tags else "General"
        wf_name = f"{primary_tag} Management"
        wf_desc = f"Group of {len(comm_endpoints)} endpoints primarily dealing with {primary_tag} operations."
        confidence = 0.5

        risk = "low"
        if "DELETE" in methods:
            risk = "critical"
        elif "POST" in methods:
            risk = "high"
        elif "PATCH" in methods or "PUT" in methods:
            risk = "medium"

        workflows_list.append(
            {
                "id": workflow_id,
                "workflow_name": wf_name,
                "risk_level": risk,
                "cluster_size": len(comm_endpoints),
                "confidence": confidence,
                "generated_description": wf_desc,
                "community_id": comm_id,
            }
        )
    t1 = time.perf_counter()
    timings["Workflow Labeling"] = t1 - t0

    # 7. Database Persistence
    t0 = time.perf_counter()
    save_endpoints(updated_endpoints)
    save_edges(edges_list)
    save_workflows(workflows_list)
    t1 = time.perf_counter()
    timings["Database Persistence"] = t1 - t0

    total_end = time.perf_counter()
    timings["Total Runtime"] = total_end - total_start

    print("\n--- BENCHMARK RESULTS ---", flush=True)
    print(f"Endpoints:  {len(endpoints)}", flush=True)
    print(f"Edges:      {len(edges_list)}", flush=True)
    print(f"Communities:{len(communities)}", flush=True)
    print(f"Workflows:  {len(workflows_list)}", flush=True)

    print("\n--- TIMING BREAKDOWN ---", flush=True)
    for stage, t in timings.items():
        if stage != "Total Runtime":
            pct = (t / timings["Total Runtime"]) * 100
            print(f"{stage:22} : {t:.4f}s ({pct:.1f}%)", flush=True)
    print(
        f"{'Total Runtime':22} : {timings['Total Runtime']:.4f}s (100.0%)", flush=True
    )


if __name__ == "__main__":
    benchmark()
