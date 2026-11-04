from app.agents.base import DesignAgent
from app.core.models import AgentResult, AgentRole, AgentTask, DesignRequest


class SpecialistAgent(DesignAgent):
    def __init__(self, role: AgentRole, description: str, focus: list[str]):
        self.role = role
        self.description = description
        self.focus = focus

    def execute(self, task: AgentTask, request: DesignRequest,
                previous: list[AgentResult]) -> AgentResult:
        prior_decisions = [d for result in previous for d in result.decisions]
        findings = [f"Evaluate {item} against the brief and product context." for item in self.focus]
        decisions = [f"Prioritize {self.focus[0]} for this project."]
        if prior_decisions:
            findings.append(f"Carry forward {len(prior_decisions)} upstream design decision(s).")
        if request.constraints:
            findings.append("Respect constraints: " + "; ".join(request.constraints))
        return AgentResult(
            task_id=task.task_id,
            role=self.role,
            summary=f"{self.description} completed its initial analysis for the supplied brief.",
            findings=findings,
            decisions=decisions,
            deliverables={"focus_areas": self.focus, "brief": request.brief},
            dependencies=task.dependencies,
            verification=["Structured result schema validated", "Project constraints propagated"],
        )
