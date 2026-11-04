from app.agents.director import DesignDirector
from app.agents.specialists import SpecialistAgent
from app.core.models import AgentRole


def build_default_registry() -> dict[AgentRole, object]:
    agents = [
        DesignDirector(),
        SpecialistAgent(AgentRole.CREATIVE, "Creative direction and concept development", [
            "originality", "art direction", "brand differentiation", "visual references"]),
        SpecialistAgent(AgentRole.UX, "User experience and information architecture", [
            "user journeys", "information hierarchy", "navigation", "accessibility"]),
        SpecialistAgent(AgentRole.VISUAL, "Visual language and composition", [
            "typography", "color system", "composition", "spacing and states"]),
        SpecialistAgent(AgentRole.SYSTEMS, "Reusable design system architecture", [
            "design tokens", "component contracts", "responsive rules", "consistency"]),
        SpecialistAgent(AgentRole.FRONTEND, "Frontend implementation planning", [
            "component architecture", "semantic markup", "responsive implementation", "performance"]),
        SpecialistAgent(AgentRole.QA, "Visual and functional quality assurance", [
            "visual regression", "interaction states", "accessibility checks", "cross-viewport validation"]),
    ]
    return {agent.role: agent for agent in agents}
