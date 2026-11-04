from app.agents.base import DesignAgent
from app.core.models import AgentResult, AgentRole, AgentTask, DesignRequest
from app.services.llm import LLMProvider, ProviderError


class SpecialistAgent(DesignAgent):
    def __init__(self, role: AgentRole, description: str, focus: list[str],
                 llm: LLMProvider | None = None):
        self.role = role
        self.description = description
        self.focus = focus
        self.llm = llm

    def execute(self, task: AgentTask, request: DesignRequest,
                previous: list[AgentResult]) -> AgentResult:
        if self.llm and self.llm.enabled:
            try:
                output = self.llm.complete_json(
                    "You are a specialist in product design and user experience. "
                    "Analyze only the supplied context. Do not claim code changes, browser "
                    "execution, or visual verification. Return JSON with summary (string), "
                    "findings (string array), decisions (string array), risks (string array), "
                    "and recommendations (string array).",
                    f"Role: {self.role.value}\nDescription: {self.description}\n"
                    f"Focus: {self.focus}\nBrief: {request.brief}\n"
                    f"Product context: {request.product_context}\n"
                    f"Platforms: {request.target_platforms}\nConstraints: {request.constraints}\n"
                    f"Upstream results: {[r.model_dump(mode='json') for r in previous]}",
                )
                return AgentResult(
                    task_id=task.task_id, role=self.role,
                    summary=str(output.get("summary", "Specialist analysis completed.")),
                    findings=self._strings(output.get("findings")),
                    decisions=self._strings(output.get("decisions")),
                    risks=self._strings(output.get("risks")),
                    deliverables={"recommendations": self._strings(output.get("recommendations")),
                                  "model_generated": True},
                    dependencies=task.dependencies,
                    verification=["Model response parsed as JSON", "Structured result schema validated"],
                )
            except ProviderError:
                # Provider failures must never make the design API unavailable.
                pass

        prior_decisions = [d for result in previous for d in result.decisions]
        findings = [f"Evaluate {item} against the brief and product context." for item in self.focus]
        decisions = [f"Prioritize {self.focus[0]} for this project."]
        if prior_decisions:
            findings.append(f"Carry forward {len(prior_decisions)} upstream design decision(s).")
        if request.constraints:
            findings.append("Respect constraints: " + "; ".join(request.constraints))
        return AgentResult(
            task_id=task.task_id, role=self.role,
            summary=f"{self.description} completed its deterministic fallback analysis.",
            findings=findings, decisions=decisions,
            deliverables={"focus_areas": self.focus, "brief": request.brief,
                          "model_generated": False},
            dependencies=task.dependencies,
            verification=["Deterministic fallback used", "Structured result schema validated",
                          "Project constraints propagated"],
        )

    @staticmethod
    def _strings(value) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, (str, int, float))]
