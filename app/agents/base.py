from abc import ABC, abstractmethod
from app.core.models import AgentResult, AgentRole, AgentTask, DesignRequest


class DesignAgent(ABC):
    role: AgentRole
    description: str

    @abstractmethod
    def execute(self, task: AgentTask, request: DesignRequest,
                previous: list[AgentResult]) -> AgentResult:
        """Execute one bounded task and return a structured handoff."""
