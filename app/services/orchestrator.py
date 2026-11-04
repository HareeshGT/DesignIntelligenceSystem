from app.agents.registry import build_default_registry
from app.core.models import AgentRole, AgentTask, DesignRequest, DesignRun, TaskStatus
from app.services.llm import LLMProvider, ProviderError
from app.services.quality import evaluate_quality


class Orchestrator:
    """Dynamic, auditable orchestration with deterministic fallback."""

    ORDER = [
        AgentRole.CREATIVE, AgentRole.UX, AgentRole.VISUAL,
        AgentRole.SYSTEMS, AgentRole.FRONTEND, AgentRole.QA,
    ]
    SPECIALISTS = set(ORDER)

    def __init__(self, memory=None, llm: LLMProvider | None = None):
        self.llm = llm or LLMProvider()
        self.registry = build_default_registry(self.llm)
        self.memory = memory
        self.last_planning_mode = "deterministic"

    def _select_roles(self, request: DesignRequest) -> list[AgentRole]:
        self.last_planning_mode = "deterministic"
        if self.llm.enabled:
            try:
                output = self.llm.complete_json(
                    "You are the planning director of a universal product design intelligence "
                    "system. Select only the specialist roles needed for this request. Return "
                    "JSON: {\"specialists\":[role strings],\"rationale\":\"...\"}. "
                    "Allowed roles: creative_director, ux_architect, visual_designer, "
                    "design_systems_engineer, frontend_engineer, visual_qa_engineer. "
                    "Select at least one role. Do not select the director.",
                    f"Brief: {request.brief}\nProduct context: {request.product_context}\n"
                    f"Platforms: {request.target_platforms}\nConstraints: {request.constraints}",
                )
                requested = output.get("specialists", [])
                roles = []
                if isinstance(requested, list):
                    for value in requested:
                        try:
                            role = AgentRole(value)
                        except (ValueError, TypeError):
                            continue
                        if role in self.SPECIALISTS and role not in roles:
                            roles.append(role)
                if roles:
                    self.last_planning_mode = "llm"
                    return [role for role in self.ORDER if role in roles]
            except ProviderError:
                pass
        return list(self.ORDER)

    def build_plan(self, request: DesignRequest) -> list[AgentTask]:
        tasks: list[AgentTask] = []
        previous_id = None
        for role in self._select_roles(request):
            task = AgentTask(
                role=role,
                objective=f"Analyze the brief from the {role.value.replace('_', ' ')} perspective.",
                context={"project_id": request.project_id,
                         "planning_mode": planning_mode},
                dependencies=[previous_id] if previous_id else [],
            )
            tasks.append(task)
            previous_id = task.task_id
        return tasks

    def run(self, request: DesignRequest) -> DesignRun:
        plan = self.build_plan(request)
        # Keep per-run metadata local so concurrent API requests cannot overwrite it.
        planning_mode = plan[0].context.get("planning_mode", "deterministic")
        results = []
        for task in plan:
            agent = self.registry[task.role]
            result = agent.execute(task, request, results)
            results.append(result)
            if self.memory:
                self.memory.append(request.project_id, "agent_result", result.model_dump(mode="json"))
        director_task = AgentTask(
            role=AgentRole.DIRECTOR,
            objective="Consolidate selected specialist work and set next actions.",
            context={"project_id": request.project_id,
                     "planning_mode": self.last_planning_mode},
            dependencies=[task.task_id for task in plan],
        )
        director_result = self.registry[AgentRole.DIRECTOR].execute(director_task, request, results)
        director_result.deliverables["planning_mode"] = planning_mode
        director_result.deliverables["selected_specialists"] = [task.role.value for task in plan]
        results.append(director_result)
        quality = evaluate_quality()
        if self.memory:
            self.memory.append(request.project_id, "design_run", {
                "brief": request.brief, "result_count": len(results), "quality": quality,
                "planning_mode": planning_mode,
                "selected_specialists": [task.role.value for task in plan],
            })
        return DesignRun(
            project_id=request.project_id, status=TaskStatus.COMPLETED,
            brief=request.brief, plan=plan, results=results, quality=quality,
        )
