"""
Dell MCP — Ingestion & Clustering Runner CLI
============================================

Orchestrates Phase 1 OpenAPI specs parsing (stripping noise) and Phase 2 graph
construction and Leiden clustering, populating the SQLite governance database.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.ai_clustering.graph_clustering import run_pipeline
from src.core.database import init_db_sync, set_pipeline_status
from src.parser.openapi_parser import OpenAPIParser
from src.ai_clustering.explain import set_explain_mode, is_explain_mode, explain_print

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the ingestion and clustering pipeline on the provided OpenAPI specification."""
    parser = argparse.ArgumentParser(
        description="Ingest and cluster OpenAPI endpoints."
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("tests/fixtures/mini_openapi.yaml"),
        help="Path to the OpenAPI JSON/YAML spec file.",
    )
    parser.add_argument(
        "--show-all-endpoints",
        action="store_true",
        help="Print every endpoint discovered in explain mode.",
    )
    args = parser.parse_args()
    
    set_explain_mode(args.explain_pipeline)

    # Set up logging format
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    import time
    start_time = time.time()

    logger.info("Initializing SQLite database...")
    init_db_sync()

    spec_path: Path = args.spec
    if not spec_path.exists():
        # Fall back to root openapi.json if it exists and mini doesn't
        root_spec = Path("openapi.json")
        if root_spec.exists():
            spec_path = root_spec
        else:
            logger.error(f"Spec file not found at '{spec_path}' or 'openapi.json'")
            return 1

    try:
        set_pipeline_status("ingestionStatus", "running")
        logger.info(f"Ingesting OpenAPI spec from: {spec_path}")
        openapi_parser = OpenAPIParser(spec_path)
        
        # ISSUE #1 - OPENAPI FILE STATS
        if is_explain_mode():
            raw_spec = openapi_parser.load_spec()
            raw_paths = raw_spec.get("paths", {})
            total_paths = len(raw_paths)
            total_ops = sum(
                1 for p in raw_paths.values() if isinstance(p, dict)
                for k in p.keys() if k.lower() in ["get", "post", "put", "patch", "delete", "options", "head", "trace"]
            )
            
            # We parse endpoints below
            contract_a = openapi_parser.parse_and_flatten()
            total_endpoints = len(contract_a.endpoints)
            
            content = (
                f"Paths Found: {total_paths}\n"
                f"Operations Found: {total_ops}\n"
                f"Endpoints Extracted: {total_endpoints}\n\n"
                f"FIRST 10 ENDPOINTS:\n"
            )
            for ep in contract_a.endpoints[:10]:
                content += f"{ep.method} {ep.url}\n"
                
            content += "\nLAST 10 ENDPOINTS:\n"
            for ep in contract_a.endpoints[-10:]:
                content += f"{ep.method} {ep.url}\n"
                
            explain_print("STAGE 1A — OPENAPI FILE STATS", content)
        else:
            contract_a = openapi_parser.parse_and_flatten()
        
        # STAGE 1: ENDPOINT EXTRACTION (ISSUE #2)
        if is_explain_mode() and args.show_all_endpoints:
            for i, ep in enumerate(contract_a.endpoints, 1):
                req_params = "\n".join(p.name for p in ep.required_params) if ep.required_params else "None"
                tags_str = ", ".join(ep.tags) if ep.tags else "None"
                content = (
                    f"operation_id:\n{ep.operation_id}\n\n"
                    f"method:\n{ep.method}\n\n"
                    f"path:\n{ep.url}\n\n"
                    f"tags:\n{tags_str}\n\n"
                    f"summary:\n{ep.summary or ''}\n\n"
                    f"required_params:\n{req_params}"
                )
                explain_print(f"ENDPOINT #{i}", content)

        set_pipeline_status("ingestionStatus", "complete")

        set_pipeline_status("graphStatus", "running")
        set_pipeline_status("clusteringStatus", "running")
        logger.info("Building relationship graph and clustering endpoints...")
        
        # Run pipeline and pass total paths for stats
        stats = run_pipeline(contract_a)
        if stats:
            stats["total_paths"] = total_paths if is_explain_mode() else len(contract_a.endpoints) # approximation if not explain mode
            
        set_pipeline_status("graphStatus", "complete")
        set_pipeline_status("clusteringStatus", "complete")

        # Set default MCP server status
        set_pipeline_status("mcpRuntimeStatus", "complete")

        # FINAL PIPELINE REPORT (ISSUE #9)
        if is_explain_mode() and stats:
            duration = time.time() - start_time
            content = (
                f"OpenAPI Paths:\n{stats.get('total_paths', 0)}\n\n"
                f"Endpoints:\n{len(contract_a.endpoints)}\n\n"
                f"Embeddings:\n{stats.get('embeddings_generated', 0)}\n\n"
                f"Graph Nodes:\n{stats.get('graph_nodes', 0)}\n\n"
                f"Graph Edges:\n{stats.get('graph_edges', 0)}\n\n"
                f"Communities:\n{stats.get('communities', 0)}\n\n"
                f"Workflows Generated:\n{stats.get('workflow_names', 0)}\n\n"
                f"LLM Success:\n{stats.get('llm_labels', 0)}\n\n"
                f"LLM Fallback:\n{stats.get('llm_fallbacks', 0)}\n\n"
                f"Saved:\n{stats.get('workflows_saved', 0)}\n\n"
                f"Duration:\n{duration:.1f} seconds\n"
            )
            explain_print("PIPELINE REPORT", content)

        logger.info("Ingestion and Graph-Clustering completed successfully.")
        return 0
    except Exception as err:
        logger.error(f"Pipeline failed: {err}")
        set_pipeline_status("ingestionStatus", "error")
        set_pipeline_status("graphStatus", "error")
        set_pipeline_status("clusteringStatus", "error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
