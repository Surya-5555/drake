import logging
from typing import Any, Dict
import httpx
from src.proxy.executors.base import BaseExecutor

logger = logging.getLogger(__name__)


class MockHTTPXExecutor(BaseExecutor):
    """
    Execution engine that routes workflow requests to a local mock REST API server.

    This executor runs asynchronously using HTTPX to prevent blocking of the event
    loop during remote server requests, fulfilling high-performance enterprise criteria.
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")

    async def execute_workflow(
        self, workflow_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes the requested workflow steps sequentially against the mock HTTP server.

        Args:
            workflow_name: Name of the workflow.
            params: Dictionary of input parameters.

        Returns:
            Dict[str, Any]: The execution execution summary.
        """
        logger.info(f"Executing workflow '{workflow_name}' via MockHTTPXExecutor")

        # Mock the async execution of workflow steps against the mock endpoint
        async with httpx.AsyncClient() as client:
            try:
                # Simulating a call to the mock endpoint
                target_url = f"{self.base_url}/redfish/v1/Systems/System.Embedded.1"
                response = await client.get(target_url, timeout=5.0)

                return {
                    "executor": "MockHTTPXExecutor",
                    "status": "success",
                    "workflow": workflow_name,
                    "mock_response_code": response.status_code,
                    "data": (
                        response.json()
                        if response.status_code == 200
                        else {"raw": response.text}
                    ),
                }
            except Exception as e:
                logger.error(f"Error during MockHTTPXExecutor execution: {e}")
                return {
                    "executor": "MockHTTPXExecutor",
                    "status": "failed",
                    "workflow": workflow_name,
                    "error": str(e),
                }
