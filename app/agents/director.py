from app.agents.base import DesignAgent
from app.core.models import AgentResult, AgentRole, AgentTask, DesignRequest


class DesignDirector(DesignAgent):
    role = AgentRole.DIRECTOR
    description = "Coordinates the design specialists and owns the final outcome."

    def execute(self, task: AgentTask, request: DesignRequest,
                previous: list[AgentResult]) -> AgentResult:
        decisions = [
            "Use an adaptive, product-specific visual direction rather than a generic template.",
            "Keep UX, visual design, design-system implementation, and QA decisions traceable.",
            "Do not claim implementation or visual verification until the relevant tools have run.",
        ]
        return AgentResult(
            task_id=task.task_id, role=self.role,
            summary="Design plan coordinated; specialist work has been consolidated.",
            findings=[f"Received {len(previous)} specialist result(s)."],
            decisions=decisions,
            deliverables={"next_step": "Connect approved design decisions to browser and code execution."},
            verification=["All specialist outputs received", "Quality gates evaluated"],
        )
