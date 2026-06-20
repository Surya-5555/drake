from pathlib import Path
from typing import Dict, Any

from src.cli.exceptions import DellCLIError
from src.core.database import get_db_connection, init_db_sync
from src.parser.openapi_parser import OpenAPIParser
from src.ai_clustering.graph_clustering import run_pipeline


class ClusterCLIService:
    """Adapter for spec ingestion and Leiden AI clustering services."""

    def run_clustering(self, spec_path: Path, explain: bool) -> Dict[str, Any]:
        if not spec_path.exists():
            raise DellCLIError(
                title="OpenAPI Spec File Missing",
                cause=f"No spec found at '{spec_path}'",
                impact="Clustering pipeline cannot be initiated.",
                action="Provide a valid path via --spec option.",
            )
        try:
            init_db_sync()
            parser = OpenAPIParser(spec_path)
            contract_a = parser.parse_and_flatten()

            # Run graph and Leiden communities sync
            from src.ai_clustering.explain import set_explain_mode

            set_explain_mode(explain)
            run_pipeline(contract_a)
            return {"status": "success"}
        except Exception as e:
            raise DellCLIError(
                title="Clustering Run Failure",
                cause=str(e),
                impact="SQLite schemas were not updated with communities.",
                action="Verify syntax of OpenAPI spec or database write permissions.",
            )

    def get_summary(self) -> Dict[str, Any]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                eps_count = conn.execute("SELECT COUNT(*) FROM endpoints").fetchone()[0]
                wfs_count = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
                comm_count = conn.execute(
                    "SELECT COUNT(DISTINCT community_id) FROM workflows"
                ).fetchone()[0]
            return {
                "Ingested Endpoints": eps_count,
                "Discovered Workflows": wfs_count,
                "Distinct Communities": comm_count,
            }
        except Exception as e:
            raise DellCLIError(
                title="Metrics Collection Failed",
                cause=str(e),
                impact="Operational summary metrics cannot be calculated.",
                action="Ensure SQLite file is not locked.",
            )

    def get_graph_stats(self) -> Dict[str, Any]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                nodes_count = conn.execute("SELECT COUNT(*) FROM endpoints").fetchone()[
                    0
                ]
                edges_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            return {"Graph Nodes": nodes_count, "Graph Edges": edges_count}
        except Exception as e:
            raise DellCLIError(
                title="Graph Diagnostics Failed",
                cause=str(e),
                impact="Relationship graph status cannot be retrieved.",
                action="Ensure governance.db exists and edges table is initialized.",
            )
