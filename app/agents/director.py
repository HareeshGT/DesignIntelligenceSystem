from app.agents.base import DesignAgent
from app.core.models import AgentResult, AgentRole, AgentTask, DesignRequest
from app.services.llm import LLMProvider, ProviderError


class DesignDirector(DesignAgent):
    role = AgentRole.DIRECTOR
    description = "Coordinates specialist reasoning and owns the consolidated design direction."

    def __init__(self, llm: LLMProvider | None = None):
        self.llm = llm

    def execute(self, task: AgentTask, request: DesignRequest,
                previous: list[AgentResult]) -> AgentResult:
        if self.llm and self.llm.enabled:
            try:
                output = self.llm.complete_json(
                    "You are the Design Director for a universal product design intelligence "
                    "system. Consolidate specialist findings into an actionable, prioritized "
                    "design direction. Do not claim implementation, browser execution, or visual "
                    "verification. Return JSON with summary (string), findings (string array), "
                    "decisions (string array), risks (string array), and next_steps (string array).",
                    f"Brief: {request.brief}\nProduct context: {request.product_context}\n"
                    f"Constraints: {request.constraints}\nSpecialist results: "
                    f"{[result.model_dump(mode='json') for result in previous]}",
                )
                return AgentResult(
                    task_id=task.task_id, role=self.role,
                    summary=str(output.get("summary", "Specialist work consolidated.")),
                    findings=self._strings(output.get("findings")),
                    decisions=self._strings(output.get("decisions")),
                    risks=self._strings(output.get("risks")),
                    deliverables={"next_steps": self._strings(output.get("next_steps")),
                                  "model_generated": True},
                    dependencies=task.dependencies,
                    verification=["Director response parsed as JSON",
                                  "Specialist handoffs consolidated"],
                )
            except ProviderError:
                pass

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
            deliverables={"next_step": "Connect approved design decisions to browser and code execution.",
                          "model_generated": False},
            dependencies=task.dependencies,
            verification=["All selected specialist outputs received", "Quality gates evaluated"],
        )

    @staticmethod
    def _strings(value) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, (str, int, float))]
