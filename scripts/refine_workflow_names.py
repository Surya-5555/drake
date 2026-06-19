import asyncio
import logging
from src.core.database import async_engine, get_db_connection
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def refine_workflow_names():
    """
    Background worker that queries unapproved workflows, generates LLM names via Ollama,
    and updates the database without blocking the main clustering pipeline.
    """
    from src.ai_clustering.ollama_service import OllamaService
    
    try:
        service = OllamaService()
    except Exception as e:
        logger.error(f"Cannot initialize OllamaService: {e}")
        return

    # Using async engine for non-blocking fetch
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT id, system_name, community_id FROM workflows WHERE approved = 0"))
        pending_workflows = [dict(r) for r in result.mappings()]

    if not pending_workflows:
        logger.info("No pending workflows to refine.")
        return

    # Fetch all endpoints to associate with communities
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM endpoints"))
        all_endpoints = [dict(r) for r in result.mappings()]

    # Group endpoints by community_id
    comm_to_endpoints = {}
    for ep in all_endpoints:
        cid = ep["community_id"]
        if cid not in comm_to_endpoints:
            comm_to_endpoints[cid] = []
        comm_to_endpoints[cid].append(ep)

    updates = []
    
    # Process each pending workflow
    for wf in pending_workflows:
        wid = wf["id"]
        sys_name = wf["system_name"]
        cid = wf["community_id"]
        endpoints = comm_to_endpoints.get(cid, [])
        
        endpoint_summaries = "\n".join(
            [f"- {ep['method']} {ep['url']} ({ep['operation_id']})" for ep in endpoints]
        )

        prompt = f"""
        You are a Dell Enterprise IT Architect naming a workflow.
        The internal deterministic system name for this workflow is: {sys_name}
        
        The underlying iDRAC API endpoints are:
        {endpoint_summaries}
        
        DO NOT alter membership.
        DO NOT invent endpoints.
        DO NOT suggest changes.

        You MUST return a JSON object containing a 'workflows' array with exactly one item.
        Set 'display_name' to a 2-6 word Title Case operational name.
        Set 'generated_description' to a single concise sentence describing its operational capability.
        """

        try:
            # Note: generate_workflow_mapping is synchronous
            logger.info(f"Refining {sys_name} ({wid})...")
            # Offload synchronous Ollama call to thread pool
            data = await asyncio.to_thread(service.generate_workflow_mapping, prompt)

            workflows = data.get("workflows", [])
            if workflows:
                llm_wf = workflows[0]
                if hasattr(llm_wf, "model_dump"):
                    llm_wf = llm_wf.model_dump()
                elif hasattr(llm_wf, "dict"):
                    llm_wf = llm_wf.dict()
                
                display_name = llm_wf.get("display_name", "")
                desc = llm_wf.get("generated_description", "")
                
                if display_name and desc:
                    updates.append({
                        "id": wid,
                        "display_name": display_name,
                        "generated_description": desc,
                        "confidence": 0.95
                    })
                    logger.info(f"Refined {wid} -> {display_name}")
        except Exception as e:
            logger.warning(f"Failed to refine {wid}: {e}")

    # Apply updates
    if updates:
        async with async_engine.begin() as conn:
            for u in updates:
                await conn.execute(
                    text("""
                    UPDATE workflows 
                    SET display_name = :display_name, 
                        generated_description = :generated_description, 
                        confidence = :confidence 
                    WHERE id = :id
                    """),
                    u
                )
        logger.info(f"Successfully refined {len(updates)} workflows.")

if __name__ == "__main__":
    asyncio.run(refine_workflow_names())
