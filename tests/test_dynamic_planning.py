from app.core.models import AgentRole, DesignRequest
from app.services.orchestrator import Orchestrator


class PlanningLLM:
    enabled = True

    def complete_json(self, system, prompt):
        return {"specialists": ["ux_architect", "visual_qa_engineer"],
                "rationale": "The request is primarily a usability review."}


def test_llm_planner_selects_only_relevant_specialists():
    orchestrator = Orchestrator(llm=PlanningLLM())
    plan = orchestrator.build_plan(DesignRequest(brief="Review checkout usability"))
    assert [task.role for task in plan] == [AgentRole.UX, AgentRole.QA]
    assert orchestrator.last_planning_mode == "llm"


def test_deterministic_fallback_keeps_all_specialists():
    orchestrator = Orchestrator()
    plan = orchestrator.build_plan(DesignRequest(brief="Design a SaaS dashboard"))
    assert [task.role for task in plan] == orchestrator.ORDER
    assert orchestrator.last_planning_mode == "deterministic"
