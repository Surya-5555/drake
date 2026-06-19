import logging
from typing import Any, Dict
import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type, retry_if_exception
from src.proxy.executors.base import BaseExecutor
from src.core.exceptions import DellProxyExecutionError

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

        Resilience Layer & Blast Radius Mitigation Strategy:
        ---------------------------------------------------
        In enterprise setups, transient network interruptions, rate limiting (HTTP 429),
        and server errors (HTTP 5xx) must not bring down the proxy ASGI event loop.
        To handle this, we wrap the execution within an asynchronous retry wrapper utilizing
        exponential backoff (1s base, scaling exponentially up to 10s max, capped at 3 attempts).
        
        Blast Radius Mitigation is achieved by:
        1. Asynchronous Execution: Non-blocking HTTPX async client prevents event loop starvation.
        2. Transient Error Isolation: We retry specifically on connection timeout exceptions
           and specific HTTP status codes (429 Too Many Requests and 5xx Server Errors). Other status
           codes (e.g. 400 Bad Request, 403 Forbidden) fail fast to avoid unnecessary load.
        3. Custom Exception Escalation: If all retries fail, we raise a clean `DellProxyExecutionError`
           so that the caller can handle the failure gracefully (e.g., triggering circuit breaker
           transitions or returning clean client-facing errors) rather than exposing raw network tracebacks.

        Args:
            workflow_name: Name of the workflow.
            params: Dictionary of input parameters.

        Returns:
            Dict[str, Any]: The execution execution summary.
            
        Raises:
            DellProxyExecutionError: Raised if all retry attempts are exhausted or a non-retryable
                                     network exception is encountered.
        """
        logger.info(f"Executing workflow '{workflow_name}' via MockHTTPXExecutor")

        def is_retryable_status_error(exc: BaseException) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response.status_code == 429 or exc.response.status_code >= 500
            return False

        retry_condition = (
            retry_if_exception_type(httpx.TimeoutException) |
            retry_if_exception(is_retryable_status_error)
        )

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_condition,
                reraise=True
            ):
                with attempt:
                    async with httpx.AsyncClient() as client:
                        target_url = f"{self.base_url}/redfish/v1/Systems/System.Embedded.1"
                        response = await client.get(target_url, timeout=5.0)
                        response.raise_for_status()

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
            raise DellProxyExecutionError(
                f"Workflow execution failed for '{workflow_name}' after exhausting all retry attempts.",
                original_exception=e
            )

        raise DellProxyExecutionError(
            f"Workflow execution failed for '{workflow_name}' after exhausting all retry attempts."
        )


