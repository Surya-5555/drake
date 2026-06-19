import logging
import re
from typing import Any, Dict, Optional
import httpx
from urllib.parse import urljoin, quote
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
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.core.database import async_session, Workflow

logger = logging.getLogger(__name__)

def resolve_expressions(value: Any, context: dict) -> Any:
    """
    Recursively resolves {{step.key}} expressions in strings, dicts, or lists
    using the provided context dictionary.
    """
    if isinstance(value, str):
        def repl(match):
            path = match.group(1).split('.')
            cur = context
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    return match.group(0)
            return str(cur)
        return re.sub(r"\{\{([\w\.]+)\}\}", repl, value)
    elif isinstance(value, dict):
        return {k: resolve_expressions(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_expressions(i, context) for i in value]
    return value


class HTTPXExecutorBase(BaseExecutor):
    """
    Base HTTPX execution engine that implements true orchestration, variable passing,
    proper URL construction, and error handling.
    """
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session_headers: Dict[str, str] = {}
        
    async def authenticate(self) -> bool:
        """Base HTTPX Executor doesn't dictate auth. Subclasses should override."""
        return True
        
    async def healthcheck(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(self.base_url, timeout=5.0)
                return res.status_code < 500
        except Exception:
            return False

    async def execute_step(self, step: Any, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a single step. Outputs become variables for future steps.
        Proper URL encoding is used instead of basic string replacement.
        """
        # Resolve any context expressions in the parameters
        resolved_params = resolve_expressions(params, context)

        # Build path carefully with url encoding
        path = step.url
        path_matches = re.findall(r"\{([a-zA-Z0-9_]+)\}", path)
        for match in path_matches:
            if match in resolved_params:
                # Use proper url encoding
                encoded_val = quote(str(resolved_params[match]))
                path = re.sub(rf"\{{{match}\}}", encoded_val, path)
            elif f"workflow.input.{match}" in context.get("workflow", {}).get("input", {}):
                encoded_val = quote(str(context["workflow"]["input"][f"workflow.input.{match}"]))
                path = re.sub(rf"\{{{match}\}}", encoded_val, path)

        target_url = urljoin(self.base_url + "/", path.lstrip("/"))

        # Extract body parameters (anything not used in path)
        body_params = {k: v for k, v in resolved_params.items() if k not in path_matches}

        req_kwargs = {"timeout": 10.0, "headers": self.session_headers.copy()}
        if step.method.lower() in ["post", "put", "patch"] and body_params:
            req_kwargs["json"] = body_params
        elif step.method.lower() in ["get", "delete", "head"] and body_params:
            req_kwargs["params"] = body_params

        def is_retryable_status_error(exc: BaseException) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response.status_code == 429 or exc.response.status_code >= 500
            return False

        retry_condition = retry_if_exception_type(httpx.TimeoutException) | retry_if_exception(is_retryable_status_error)

        async with httpx.AsyncClient() as client:
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=10),
                    retry=retry_condition,
                    reraise=True,
                ):
                    with attempt:
                        response = await client.request(step.method.upper(), target_url, **req_kwargs)
                        response.raise_for_status()

                        try:
                            data = response.json()
                            data = compress_redfish_response(data)
                        except ValueError:
                            data = {"raw": response.text}
                            
                        return {
                            "step_id": step.id,
                            "method": step.method.upper(),
                            "url": target_url,
                            "status_code": response.status_code,
                            "data": data,
                        }
            except Exception as e:
                logger.error(f"Error during step '{step.url}' execution: {e}")
                raise DellProxyExecutionError(
                    f"Workflow step execution failed for '{target_url}' after exhausting retries.",
                    original_exception=e,
                )

    async def execute_workflow(self, workflow_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Executing workflow '{workflow_name}' via {self.__class__.__name__}")
        await self.authenticate()

        async with async_session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.system_name == workflow_name).options(selectinload(Workflow.steps))
            )
            wf = result.scalar_one_or_none()
            if not wf:
                raise DellProxyExecutionError(f"Workflow '{workflow_name}' not found.")
            steps = wf.steps

        # Initialize workflow context with input parameters
        context = {
            "workflow": {
                "input": params
            }
        }
        
        step_results = []
        for idx, step in enumerate(steps):
            step_name = f"step{idx+1}"
            try:
                res = await self.execute_step(step, params, context)
                step_results.append(res)
                # Store output in context for future steps
                context[step_name] = res["data"]
            except Exception as e:
                return {
                    "workflow_id": wf.id,
                    "status": "partial_failure",
                    "steps_executed": len(step_results),
                    "failed_step": step_name,
                    "error": str(e),
                    "step_results": step_results,
                }

        return {
            "workflow_id": wf.id,
            "status": "success",
            "steps_executed": len(step_results),
            "step_results": step_results,
            "context": context
        }


class PrismExecutor(HTTPXExecutorBase):
    """
    Execution engine for Hackathon environment targeting the Stoplight Prism mock server.
    """
    def __init__(self, base_url: str = "http://localhost:4010") -> None:
        super().__init__(base_url)

    async def authenticate(self) -> bool:
        # Prism doesn't require actual authentication, but we simulate header injection
        self.session_headers["Authorization"] = "Bearer prism-mock-token"
        return True


class MockExecutor(HTTPXExecutorBase):
    """
    Offline Mock Executor for fallback scenarios when Prism is not available.
    """
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        super().__init__(base_url)

    async def authenticate(self) -> bool:
        self.session_headers["Authorization"] = "Basic mock-offline-token"
        return True

# For backwards compatibility during transition
MockHTTPXExecutor = MockExecutor
