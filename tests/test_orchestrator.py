from app.core.models import AgentRole, DesignRequest
from app.services.orchestrator import Orchestrator


def test_registry_contains_all_six_specialists_and_director():
    registry = Orchestrator().registry
    assert set(registry) == set(AgentRole)


def test_orchestrator_runs_all_specialists_and_director():
    run = Orchestrator().run(DesignRequest(brief="Design a modern analytics dashboard"))
    assert len(run.plan) == 6
    assert len(run.results) == 7
    assert run.results[-1].role == AgentRole.DIRECTOR
    assert run.status.value == "completed"


def test_plan_dependencies_are_sequential_and_traceable():
    plan = Orchestrator().build_plan(DesignRequest(brief="Create a product landing page"))
    assert plan[0].dependencies == []
    for previous, current in zip(plan, plan[1:]):
        assert current.dependencies == [previous.task_id]


def test_constraints_reach_agent_outputs():
    request = DesignRequest(brief="Redesign a mobile dashboard", constraints=["WCAG AA", "mobile first"])
    run = Orchestrator().run(request)
    assert all(any("WCAG AA" in finding for finding in result.findings)
               for result in run.results[:6])
