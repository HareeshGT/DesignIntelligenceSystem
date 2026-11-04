from app.agents.registry import build_default_registry
from app.core.models import AgentRole, AgentTask, DesignRequest, DesignRun, TaskStatus
from app.services.quality import evaluate_quality


class Orchestrator:
    """Deterministic, auditable first-pass orchestration; provider-backed reasoning is pluggable."""
    ORDER = [
        AgentRole.CREATIVE, AgentRole.UX, AgentRole.VISUAL,
        AgentRole.SYSTEMS, AgentRole.FRONTEND, AgentRole.QA,
    ]

    def __init__(self, memory=None):
        self.registry = build_default_registry()
        self.memory = memory

    def build_plan(self, request: DesignRequest) -> list[AgentTask]:
        tasks: list[AgentTask] = []
        previous_id = None
        for role in self.ORDER:
            task = AgentTask(
                role=role,
                objective=f"Analyze the brief from the {role.value.replace('_', ' ')} perspective.",
                context={"project_id": request.project_id},
                dependencies=[previous_id] if previous_id else [],
            )
            tasks.append(task)
            previous_id = task.task_id
        return tasks

    def run(self, request: DesignRequest) -> DesignRun:
        plan = self.build_plan(request)
        results = []
        for task in plan:
            agent = self.registry[task.role]
            result = agent.execute(task, request, results)
            results.append(result)
            if self.memory:
                self.memory.append(request.project_id, "agent_result", result.model_dump(mode="json"))
        director_task = AgentTask(
            role=AgentRole.DIRECTOR,
            objective="Consolidate specialist work and set next actions.",
            context={"project_id": request.project_id},
            dependencies=[task.task_id for task in plan],
        )
        director_result = self.registry[AgentRole.DIRECTOR].execute(director_task, request, results)
        results.append(director_result)
        quality = evaluate_quality()
        if self.memory:
            self.memory.append(request.project_id, "design_run", {
                "brief": request.brief, "result_count": len(results), "quality": quality,
            })
        return DesignRun(
            project_id=request.project_id, status=TaskStatus.COMPLETED,
            brief=request.brief, plan=plan, results=results, quality=quality,
        )
