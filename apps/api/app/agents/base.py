"""BaseAgent abstract class defining the agent interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AgentContext:
    """Shared context object passed between agent steps."""

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id
        self.data: Dict[str, Any] = {}
        self.artifacts: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def add_artifact(self, name: str, content: Any) -> None:
        self.artifacts[name] = content


class AgentResult:
    """Result of an agent execution."""

    def __init__(
        self,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        result = {"success": self.success}
        if self.output is not None:
            result["output"] = self.output
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class BaseAgent(ABC):
    """Abstract base class for all agents in the pipeline."""

    name: str = "base_agent"
    description: str = ""

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute the agent's task within the given context.

        Args:
            context: Shared context containing project data and prior agent results.

        Returns:
            AgentResult with success status and output data.
        """

    @abstractmethod
    async def validate_input(self, context: AgentContext) -> bool:
        """Validate that the context contains required inputs.

        Returns True if all required inputs are present.
        """

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description
