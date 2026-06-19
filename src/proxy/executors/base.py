import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class BaseExecutor(ABC):
    """
    Abstract Base Class for workflow execution engines using Hexagonal Architecture (Ports & Adapters).

    This interface strictly isolates business logic from infrastructure implementation.
    The workflow engine only communicates through these abstract methods, 
    allowing seamless fallback between:
      1. DellExecutor (Production hardware API/OMSDK)
      2. PrismExecutor (Hackathon mock server)
      3. MockExecutor (Offline hardcoded logic fallback)
    """

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate the executor session. Should support Bearer, Basic, API Key, etc.,
        based on provider implementation.
        """
        pass

    @abstractmethod
    async def healthcheck(self) -> bool:
        """
        Perform a healthcheck against the target provider.
        """
        pass

    @abstractmethod
    async def execute_step(self, step: Any, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a single step. 
        Context contains outputs of previous steps mapped for variable substitution.
        """
        pass

    @abstractmethod
    async def execute_workflow(
        self, workflow_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Asynchronously execute a clustered workflow orchestrating multiple steps.
        
        Args:
            workflow_name: The name/identifier of the clustered workflow to execute.
            params: Key-value parameters resolved and validated by the translation layer.

        Returns:
            Dict[str, Any]: Execution result details, statuses, or payloads.
        """
        pass
