import pytest


def test_approved_workflows_become_mcp_tools(mcp_pipeline, approved_workflow):
    """1. Approved workflows become MCP tools"""
    tools = mcp_pipeline.get_registered_tools()
    assert approved_workflow.name in [tool.name for tool in tools]


def test_rejected_workflows_do_not_become_tools(mcp_pipeline, rejected_workflow):
    """2. Rejected workflows do not become tools"""
    tools = mcp_pipeline.get_registered_tools()
    assert rejected_workflow.name not in [tool.name for tool in tools]


def test_tool_name_matches_workflow_name(mcp_pipeline, approved_workflow):
    """3. Tool name matches workflow name"""
    tool = mcp_pipeline.get_tool(approved_workflow.name)
    assert tool is not None
    assert tool.name == approved_workflow.name


def test_dynamic_reload_works(mcp_pipeline, newly_approved_workflow):
    """4. Dynamic reload works"""
    # Initially not a tool
    tools = mcp_pipeline.get_registered_tools()
    assert newly_approved_workflow.name not in [tool.name for tool in tools]

    # Reload triggers tool addition
    mcp_pipeline.reload()

    # Now it should be a tool
    tools = mcp_pipeline.get_registered_tools()
    assert newly_approved_workflow.name in [tool.name for tool in tools]
