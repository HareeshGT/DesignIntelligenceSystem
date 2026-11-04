from app.agents.director import DesignDirector
from app.agents.specialists import SpecialistAgent
from app.core.models import AgentRole
from app.services.llm import LLMProvider


def build_default_registry(llm: LLMProvider | None = None) -> dict[AgentRole, object]:
    agents = [
        DesignDirector(llm),
        SpecialistAgent(AgentRole.CREATIVE, "Creative direction and concept development", [
            "originality", "art direction", "brand differentiation", "visual references"], llm),
        SpecialistAgent(AgentRole.UX, "User experience and information architecture", [
            "user journeys", "information hierarchy", "navigation", "accessibility"], llm),
        SpecialistAgent(AgentRole.VISUAL, "Visual language and composition", [
            "typography", "color system", "composition", "spacing and states"], llm),
        SpecialistAgent(AgentRole.SYSTEMS, "Reusable design system architecture", [
            "design tokens", "component contracts", "responsive rules", "consistency"], llm),
        SpecialistAgent(AgentRole.FRONTEND, "Frontend implementation planning", [
            "component architecture", "semantic markup", "responsive implementation", "performance"], llm),
        SpecialistAgent(AgentRole.QA, "Visual and functional quality assurance", [
            "visual regression", "interaction states", "accessibility checks", "cross-viewport validation"], llm),
    ]
    return {agent.role: agent for agent in agents}
