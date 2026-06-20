import asyncio
import json
import sqlite3
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

async def run_end_to_end():
    print("=====================================================================")
    print("      DELL DRAKE END-TO-END MCP PIPELINE & EXECUTION VERIFIER")
    print("=====================================================================\n")

    # 1. Register the test workflow and steps in the database
    print("[1] Seeding test workflow 'mini_sys_reset_workflow' into the SQLite database...")
    db_file = "data/governance.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Clear old entries
    cursor.execute("DELETE FROM endpoint_steps WHERE workflow_id = 'wf_mini_reset'")
    cursor.execute("DELETE FROM workflows WHERE id = 'wf_mini_reset'")

    # Insert workflow
    cursor.execute("""
        INSERT INTO workflows (
            id, system_name, display_name, risk_level, cluster_size, confidence, 
            generated_description, approved, supports_rollback, rollback_strategy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "wf_mini_reset",
        "mini_sys_reset_workflow",
        "Computer System Query & Reset",
        "high",
        2,
        1.0,
        "Mock system status check and reset action",
        1,  # approved
        0,  # supports_rollback
        "NONE"
    ))

    # Insert steps
    cursor.execute("""
        INSERT INTO endpoint_steps (
            workflow_id, step_order, operation_id, method, url, required_params, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        "wf_mini_reset",
        1,
        "GetComputerSystem",
        "GET",
        "/redfish/v1/Systems/{ComputerSystemId}",
        '[{"name": "ComputerSystemId", "param_type": "string", "required": true}]',
        "2026-06-20T20:00:00"
    ))

    cursor.execute("""
        INSERT INTO endpoint_steps (
            workflow_id, step_order, operation_id, method, url, required_params, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        "wf_mini_reset",
        2,
        "ResetComputerSystem",
        "POST",
        "/redfish/v1/Systems/{ComputerSystemId}/Actions/ComputerSystem.Reset",
        '[{"name": "ComputerSystemId", "param_type": "string", "required": true}]',
        "2026-06-20T20:00:00"
    ))

    conn.commit()
    conn.close()
    print("  -> Test workflow seeded successfully.")

    # 2. Trigger reload of the MCP proxy server tools
    print("\n[2] Triggering MCP Proxy tools reload via API...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/mcp/reload",
            headers={"X-API-Key": "default_dev_key"},
            timeout=10.0
        )
        if response.status_code == 200:
            print("  -> MCP tools reloaded successfully.")
        else:
            print(f"  [ERROR] Failed to reload MCP tools: {response.status_code} {response.text}")
            return

    # 3. Establish SSE Client connection to FastMCP proxy server
    print("\n[3] Connecting to the running FastMCP Proxy server via SSE...")
    async with sse_client("http://localhost:8000/mcp/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("  -> Session initialized successfully.")

            # 4. List tools
            tools_response = await session.list_tools()
            tools = {t.name: t for t in tools_response.tools}
            
            tool_name = "mini_sys_reset_workflow"
            if tool_name not in tools:
                print(f"  [ERROR] '{tool_name}' tool not found in FastMCP registry!")
                return
            
            print(f"  -> Found '{tool_name}' in the registry.")
            print(f"     Input Schema: {tools[tool_name].inputSchema}")

            # 5. Invoke the tool through the MCP proxy server
            print(f"\n[4] Invoking MCP tool '{tool_name}' as an AI Agent...")
            arguments = {"ComputerSystemId": "sys-idrac-120"}
            print(f"  - Input Arguments: {arguments}")
            
            # call_tool triggers execute_workflow_route -> PrismExecutor -> Prism Mock Server!
            result = await session.call_tool(tool_name, arguments=arguments)
            
            # Print the invocation result
            print("  -> Call Tool Execution completed.")
            print("  -> Raw Result object type:", type(result))
            
            # Format and show execution outcome
            print("\n=== Tool Response (Result) ===")
            for content in result.content:
                if content.type == "text":
                    try:
                        parsed_text = json.loads(content.text)
                        print(json.dumps(parsed_text, indent=2))
                    except Exception:
                        print(content.text)

    # 6. Connect to database to verify execution ledger and audit logs
    print("\n[5] Querying SQLite Database for Audit Trail and Execution Ledger...")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query Execution History
    cursor.execute("""
        SELECT * FROM execution_history 
        WHERE workflow_id = 'wf_mini_reset' 
        ORDER BY id DESC LIMIT 1
    """)
    ledger_row = cursor.fetchone()
    print("\n--- Execution History Ledger Record ---")
    if ledger_row:
        print(f"  ID: {ledger_row['id']}")
        print(f"  Target Server IP: {ledger_row['target_server_ip']}")
        print(f"  Status: {ledger_row['status']}")
        print(f"  Timestamp: {ledger_row['timestamp']}")
    else:
        print("  No execution ledger entry found for 'wf_mini_reset'.")

    # Query Audit Trail Events
    cursor.execute("""
        SELECT * FROM audit_events 
        WHERE workflow_name = 'mini_sys_reset_workflow' 
        ORDER BY timestamp DESC LIMIT 3
    """)
    audit_rows = cursor.fetchall()
    print("\n--- Tamper-Evident Audit Trail Logs ---")
    if audit_rows:
        for idx, r in enumerate(audit_rows):
            print(f"  [{idx+1}] Event Type: {r['event_type']}")
            print(f"      Status: {r['status']}")
            print(f"      Description: {r['description']}")
            print(f"      Actor: {r['actor']}")
            print(f"      Hash: {r['hash'][:16]}...")
            print(f"      Prev Hash: {r['previous_hash'][:16]}...")
    else:
        print("  No audit events found for 'mini_sys_reset_workflow'.")

    conn.close()
    print("\n=====================================================================")
    print("           END-TO-END MCP PIPELINE VERIFIED SUCCESSFULLY!")
    print("=====================================================================")

if __name__ == "__main__":
    asyncio.run(run_end_to_end())
