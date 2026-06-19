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
        "--explain-pipeline",
        action="store_true",
        help="Enable live pipeline explain mode to stream detailed stages to the terminal.",
    )
    args = parser.parse_args()
    
    set_explain_mode(args.explain_pipeline)

    # Set up logging format
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

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
        contract_a = openapi_parser.parse_and_flatten()
        
        # STAGE 1: ENDPOINT EXTRACTION
        if is_explain_mode():
            content = ""
            for i, ep in enumerate(contract_a.endpoints, 1):
                content += f"[{i}/{len(contract_a.endpoints)}]\n\n"
                content += f"operation_id:\n{ep.operation_id}\n\n"
                content += f"method:\n{ep.method}\n\n"
                content += f"path:\n{ep.url}\n\n"
                
                tags_str = '["' + '", "'.join(ep.tags) + '"]' if ep.tags else '[]'
                content += f"tags:\n{tags_str}\n\n"
                
                summary = ep.summary if ep.summary else ""
                content += f"summary:\n{summary}\n\n"
                content += "-" * 50 + "\n\n"
                
            content += f"Total Endpoints:\n{len(contract_a.endpoints)}"
            explain_print("PARSED ENDPOINTS", content)

        set_pipeline_status("ingestionStatus", "complete")

        set_pipeline_status("graphStatus", "running")
        set_pipeline_status("clusteringStatus", "running")
        logger.info("Building relationship graph and clustering endpoints...")
        stats = run_pipeline(contract_a)
        set_pipeline_status("graphStatus", "complete")
        set_pipeline_status("clusteringStatus", "complete")

        # Set default MCP server status
        set_pipeline_status("mcpRuntimeStatus", "complete")

        # FINAL PIPELINE REPORT
        if is_explain_mode() and stats:
            content = (
                f"Endpoints Parsed:\n{len(contract_a.endpoints)}\n\n"
                f"Embeddings Generated:\n{stats.get('embeddings_generated', 0)}\n\n"
                f"Graph Nodes:\n{stats.get('graph_nodes', 0)}\n\n"
                f"Graph Edges:\n{stats.get('graph_edges', 0)}\n\n"
                f"Communities:\n{stats.get('communities', 0)}\n\n"
                f"Workflow Names Generated:\n{stats.get('workflow_names', 0)}\n\n"
                f"LLM Labels Generated:\n{stats.get('llm_labels', 0)}\n\n"
                f"Workflows Saved:\n{stats.get('workflows_saved', 0)}\n"
            )
            explain_print("PIPELINE EXECUTION REPORT", content)
            explain_print("PIPELINE COMPLETED SUCCESSFULLY", "")

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
