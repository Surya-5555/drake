import time
import os
import logging
from src.parser.openapi_parser import OpenAPIParser
from src.ai_clustering.graph_clustering import build_relationship_graph, detect_communities

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Benchmark")

def run_benchmark():
    spec_path = "data/openapi_sample.json"
    if not os.path.exists(spec_path):
        logger.error(f"Cannot find {spec_path} for benchmarking.")
        return

    logger.info("Starting Enterprise Benchmark Pipeline...")
    
    t0 = time.time()
    
    # Phase 1: Parse
    parser = OpenAPIParser(spec_path)
    contract_a = parser.parse_and_flatten()
    t1 = time.time()
    
    logger.info(f"Parsed {len(contract_a.endpoints)} endpoints in {t1 - t0:.2f} seconds.")

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
    
    t2 = time.time()
    
    # Phase 2: Graph Build
    logger.info("Building Relationship Graph...")
    G = build_relationship_graph(endpoints)
    t3 = time.time()
    
    logger.info(f"Graph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges in {t3 - t2:.2f} seconds.")
    
    # Phase 3: Community Detection
    logger.info("Detecting Communities...")
    communities = detect_communities(G)
    t4 = time.time()
    
    logger.info(f"Detected {len(communities)} communities in {t4 - t3:.2f} seconds.")
    
    # Diagnostics
    sizes = [len(c) for c in communities]
    avg_size = sum(sizes) / len(sizes) if sizes else 0
    max_size = max(sizes) if sizes else 0
    min_size = min(sizes) if sizes else 0
    singletons = sum(1 for s in sizes if s == 1)
    
    logger.info(f"Community distribution -> Avg: {avg_size:.1f}, Max: {max_size}, Min: {min_size}, Singletons: {singletons}")
    logger.info(f"Total Pipeline Runtime: {t4 - t0:.2f} seconds.")

if __name__ == "__main__":
    run_benchmark()
