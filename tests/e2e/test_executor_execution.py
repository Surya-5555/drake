import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.proxy.executors.httpx_executor import MockHTTPXExecutor
from src.core.database import Workflow, EndpointStep
from src.core.exceptions import DellProxyExecutionError


@pytest.mark.asyncio
@patch("src.proxy.executors.httpx_executor.async_session")
@patch("src.proxy.executors.httpx_executor.httpx.AsyncClient")
async def test_mock_httpx_executor_success(mock_async_client, mock_async_session):
    # Setup mock DB session
    mock_session = AsyncMock()
    mock_result = MagicMock()

    # Mock workflow steps
    step1 = EndpointStep(id=1, url="/systems/{system_id}", method="GET")
    step2 = EndpointStep(id=2, url="/systems/{system_id}/reset", method="POST")

    mock_wf = Workflow(id="wf_1", workflow_name="test_wf", steps=[step1, step2])

    mock_result.scalar_one_or_none.return_value = mock_wf
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Configure context manager
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_async_session.return_value = mock_session_ctx

    # Mock HTTP responses
    mock_client_instance = AsyncMock()
    mock_resp_1 = MagicMock()
    mock_resp_1.status_code = 200
    mock_resp_1.json.return_value = {"sys": "data"}

    mock_resp_2 = MagicMock()
    mock_resp_2.status_code = 202
    mock_resp_2.json.return_value = {"reset": "ok"}

    # Make request return responses in sequence
    mock_client_instance.request = AsyncMock(side_effect=[mock_resp_1, mock_resp_2])

    mock_client_ctx = MagicMock()
    mock_client_ctx.__aenter__.return_value = mock_client_instance
    mock_async_client.return_value = mock_client_ctx

    # Execute
    executor = MockHTTPXExecutor(base_url="http://fake")
    result = await executor.execute_workflow(
        "test_wf", {"system_id": "sys123", "force": "true"}
    )

    assert result["status"] == "success"
    assert result["steps_executed"] == 2

    assert result["step_results"][0]["url"] == "http://fake/systems/sys123"
    assert result["step_results"][0]["method"] == "GET"

    assert result["step_results"][1]["url"] == "http://fake/systems/sys123/reset"
    assert result["step_results"][1]["method"] == "POST"

    # Verify requests were called correctly
    # GET shouldn't have JSON body
    mock_client_instance.request.assert_any_call(
        "GET", "http://fake/systems/sys123", timeout=5.0
    )
    # POST should have remaining param 'force' in JSON body
    mock_client_instance.request.assert_any_call(
        "POST", "http://fake/systems/sys123/reset", timeout=5.0, json={"force": "true"}
    )
