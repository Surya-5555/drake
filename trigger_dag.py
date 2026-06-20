import sqlite3
from src.ai_clustering.dependency_matcher import build_execution_dag

def run():
    conn = sqlite3.connect('data/governance.db')
    conn.row_factory = sqlite3.Row
    
    # Get all workflows
    wfs = [dict(r) for r in conn.execute("SELECT * FROM workflows")]
    
    for wf in wfs:
        wf_id = wf["id"]
        comm_id = wf.get("community_id", wf_id)
        
        # Get endpoints for this community
        eps = [dict(r) for r in conn.execute("SELECT * FROM endpoints WHERE community_id = ?", (comm_id,))]
        
        # DAG Sort
        sorted_eps = build_execution_dag(eps)
        
        # Clear existing steps and reinsert
        conn.execute("DELETE FROM endpoint_steps WHERE workflow_id = ?", (wf_id,))
        
        for i, ep in enumerate(sorted_eps):
            conn.execute(
                """
                INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, request_schema, response_schema, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    wf_id,
                    i + 1,
                    ep["operation_id"],
                    ep["method"],
                    ep["url"],
                    ep["required_params"],
                    ep.get("request_schema"),
                    ep.get("response_schema")
                )
            )
            
    conn.commit()
    print("DAG sort applied successfully to all workflows!")

if __name__ == "__main__":
    run()
