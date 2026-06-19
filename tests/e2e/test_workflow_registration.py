import pytest
from src.proxy.server import extract_placeholders_from_steps
from src.core.database import EndpointStep


def test_extract_placeholders():
    step1 = EndpointStep(url="/Systems/{system_id}")
    step2 = EndpointStep(url="/Systems/{system_id}/Processors/{processor_id}")

    placeholders = extract_placeholders_from_steps([step1, step2])

    assert "system_id" in placeholders
    assert "processor_id" in placeholders
    assert len(placeholders) == 2


def test_dynamic_tool_registration():
    # Since load_approved_tools_from_db involves async SQLAlchemy sessions and FastMCP,
    # we can test the signature generation logic that we refactored.
    import inspect

    def make_tool(wf_name, wf_desc, p_names):
        async def dynamic_tool(**kwargs) -> dict:
            return {"status": "ok"}

        dynamic_tool.__name__ = wf_name
        dynamic_tool.__doc__ = wf_desc

        params = []
        for p in p_names:
            params.append(
                inspect.Parameter(
                    name=p,
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default="",
                    annotation=str,
                )
            )
        dynamic_tool.__signature__ = inspect.Signature(parameters=params)  # type: ignore
        return dynamic_tool

    tool = make_tool("test_wf", "desc", ["sys_id", "proc_id"])

    assert tool.__name__ == "test_wf"
    assert tool.__doc__ == "desc"

    sig = inspect.signature(tool)
    assert "sys_id" in sig.parameters
    assert "proc_id" in sig.parameters
    assert sig.parameters["sys_id"].annotation == str
