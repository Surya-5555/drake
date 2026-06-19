import logging
from typing import Any, Dict
import httpx
from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
)
from src.proxy.executors.base import BaseExecutor
from src.core.exceptions import DellProxyExecutionError
from src.core.compression import compress_redfish_response

logger = logging.getLogger(__name__)


import re
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.core.database import async_session, Workflow


class MockHTTPXExecutor(BaseExecutor):
    """
    Execution engine that routes workflow requests to a local mock REST API server.
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")

    async def execute_workflow(
        self, workflow_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes the requested workflow steps sequentially against the mock HTTP server.
        """
        logger.info(f"Executing workflow '{workflow_name}' via MockHTTPXExecutor")

        async with async_session() as session:
            result = await session.execute(
                select(Workflow)
                .where(Workflow.system_name == workflow_name)
                .options(selectinload(Workflow.steps))
            )
            wf = result.scalar_one_or_none()
            if not wf:
                raise DellProxyExecutionError(f"Workflow '{workflow_name}' not found.")

            steps = wf.steps

        step_results = []

        def is_retryable_status_error(exc: BaseException) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return (
                    exc.response.status_code == 429 or exc.response.status_code >= 500
                )
            return False

        retry_condition = retry_if_exception_type(
            httpx.TimeoutException
        ) | retry_if_exception(is_retryable_status_error)

        async with httpx.AsyncClient() as client:
            for step in steps:
                target_url = self.base_url + step.url

                # Substitute placeholders
                for match in re.findall(r"\{([a-zA-Z0-9_]+)\}", step.url):
                    if match in params:
                        target_url = target_url.replace(
                            f"{{{match}}}", str(params[match])
                        )

                # Extract body parameters
                body_params = {
                    k: v for k, v in params.items() if f"{{{k}}}" not in step.url
                }

                req_kwargs = {"timeout": 5.0}
                if step.method.lower() in ["post", "put", "patch"] and body_params:
                    req_kwargs["json"] = body_params

                try:
                    async for attempt in AsyncRetrying(
                        stop=stop_after_attempt(3),
                        wait=wait_exponential(multiplier=1, min=1, max=10),
                        retry=retry_condition,
                        reraise=True,
                    ):
                        with attempt:
                            response = await client.request(
                                step.method.upper(), target_url, **req_kwargs
                            )
                            response.raise_for_status()

                            try:
                                data = response.json()
                                data = compress_redfish_response(data)
                            except ValueError:
                                data = {"raw": response.text}

                            step_results.append(
                                {
                                    "step_id": step.id,
                                    "method": step.method.upper(),
                                    "url": target_url,
                                    "status_code": response.status_code,
                                    "data": data,
                                }
                            )
                except Exception as e:
                    logger.error(f"Error during step '{step.url}' execution: {e}")
                    raise DellProxyExecutionError(
                        f"Workflow step execution failed for '{workflow_name}' on '{step.url}' after exhausting retries.",
                        original_exception=e,
                    )

        return {
            "workflow_id": wf.id,
            "status": "success",
            "steps_executed": len(step_results),
            "step_results": step_results,
        }
