import pytest

def test_complete_system_pipeline(
    mock_openapi_spec,
    parser_pipeline,
    graph_pipeline,
    workflow_pipeline,
    db_pipeline,
    approval_pipeline,
    mcp_pipeline,
    execution_engine,
    compression_engine
):
    """
    OpenAPI -> Parser -> Graph -> Workflow Discovery -> 
    Database -> Approval -> MCP Registration -> 
    Execution -> Compression -> Response
    """
    # 1. Parse
    parser_pipeline.load_spec(mock_openapi_spec)
    endpoints = parser_pipeline.get_endpoints()
    assert len(endpoints) > 0
    
    # 2. Graph Builder
    graph_pipeline.build(endpoints)
    assert graph_pipeline.get_node_count() == len(endpoints)
    
    # 3. Workflow Discovery
    workflow_pipeline.discover(graph_pipeline)
    workflows = workflow_pipeline.get_workflows()
    assert len(workflows) > 0
    
    # 4. Save to DB
    for wf in workflows:
        db_pipeline.save_workflow(wf)
        
    # 5. Approval (Approve first workflow)
    first_wf = workflows[0]
    approval_pipeline.approve(first_wf.id)
    
    # 6. MCP Registration
    mcp_pipeline.reload()
    tools = mcp_pipeline.get_registered_tools()
    assert first_wf.name in [tool.name for tool in tools]
    
    # 7. Execution
    result = execution_engine.execute(first_wf)
    assert result.success is True
    
    # 8. Compression
    compressed = compression_engine.compress(result.data)
    assert compressed is not None
    assert "@odata.id" not in compressed
