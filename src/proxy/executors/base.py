from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseExecutor(ABC):
    """
    Abstract Base Class for workflow execution engines.

    This interface separates the translation logic (FastMCP tools and routing)
    from the target-system communication implementation. By adhering to the
    Interface Segregation Principle, this allows hot-swapping between:
      1. An HTTPX-based executor (for mock testing, local offline verification,
         and REST-based environment targets).
      2. Dell's official OpenManage Python SDK (omsdk) or redfish API executor
         (for production hardware interaction).
    """

    @abstractmethod
    async def execute_workflow(
        self, workflow_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Asynchronously execute a clustered workflow.

        Args:
            workflow_name: The name/identifier of the clustered workflow to execute.
            params: Key-value parameters resolved and validated by the
                translation layer.

        Returns:
            Dict[str, Any]: The execution result details, statuses, or payloads.
        """
        pass
