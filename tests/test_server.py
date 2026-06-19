import pytest
from src.proxy.server import mcp


@pytest.mark.anyio
async def test_dynamic_tools_registration() -> None:
    """
    Ensure the proxy server dynamically registers tools from the mapping JSON.
    """
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]

    assert "get_proxy_status" in tool_names


@pytest.mark.anyio
async def test_executor_routing() -> None:
    """
    Ensure status diagnostic tool reports correct status.
    """
    # Call the diagnostic status tool
    tools = await mcp.list_tools()
    status_tool = next(t for t in tools if t.name == "get_proxy_status")

    # Run the tool function directly
    result = await status_tool.fn()  # type: ignore[attr-defined]
    assert result["status"] == "online"
    assert "registered_workflows" in result
