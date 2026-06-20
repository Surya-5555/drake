import asyncio
import logging
from pathlib import Path

from src.parser.openapi_parser import OpenAPIParser
from src.ai_clustering.graph_clustering import run_pipeline
from src.core.database import init_db_sync
from scripts.refine_workflow_names import refine_workflow_names

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProductionPipeline")

def main():
    from src.core.database import set_pipeline_status
    
    logger.info("Initializing Governance Database...")
    init_db_sync()

    set_pipeline_status("ingestionStatus", "running")
    set_pipeline_status("graphStatus", "running")
    set_pipeline_status("clusteringStatus", "running")

    root_dir = Path(__file__).resolve().parent.parent
    spec_path = root_dir / "tests" / "fixtures" / "openapi-7.xx.yaml"
    
    logger.info(f"Parsing OpenAPI spec from {spec_path}...")
    parser = OpenAPIParser(spec_path)
    contract_a = parser.parse_and_flatten()
    
    set_pipeline_status("ingestionStatus", "complete")

    logger.info(f"Parsed {len(contract_a.endpoints)} endpoints. Starting mathematically rigorous clustering pipeline...")
    
    # This executes SentenceTransformers embeddings, Cosine Similarity, and Leiden clustering
    stats = run_pipeline(contract_a)
    logger.info(f"Mathematical Clustering complete. Stats: {stats}")
    
    set_pipeline_status("graphStatus", "complete")
    set_pipeline_status("clusteringStatus", "complete")

    logger.info("Starting LLM optimization using local Qwen model to refine workflow names...")
    # This hits Ollama asynchronously to optimize the generated system_names
    try:
        asyncio.run(refine_workflow_names())
    except Exception as e:
        logger.warning(f"Refine workflow names failed: {e}")
        
    set_pipeline_status("mcpRuntimeStatus", "complete")
    
    logger.info("Production Pipeline Completed Successfully! You can now check your Governance Console.")

if __name__ == "__main__":
    main()
