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
from src.core.database import init_db, set_pipeline_status
from src.parser.openapi_parser import OpenAPIParser

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the ingestion and clustering pipeline on the provided OpenAPI specification."""
    parser = argparse.ArgumentParser(description="Ingest and cluster OpenAPI endpoints.")
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("tests/fixtures/mini_openapi.yaml"),
        help="Path to the OpenAPI JSON/YAML spec file.",
    )
    args = parser.parse_args()

    # Set up logging format
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    logger.info("Initializing SQLite database...")
    init_db()

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
        parser = OpenAPIParser(spec_path)
        contract_a = parser.parse_and_flatten()
        set_pipeline_status("ingestionStatus", "complete")

        set_pipeline_status("graphStatus", "running")
        set_pipeline_status("clusteringStatus", "running")
        logger.info("Building relationship graph and clustering endpoints...")
        run_pipeline(contract_a)
        set_pipeline_status("graphStatus", "complete")
        set_pipeline_status("clusteringStatus", "complete")

        # Set default MCP server status
        set_pipeline_status("mcpRuntimeStatus", "complete")

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
