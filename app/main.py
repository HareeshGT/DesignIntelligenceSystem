from dotenv import load_dotenv
from fastapi import FastAPI

# Load local development configuration before constructing provider clients.
load_dotenv()

from app.api.repositories import router as repositories_router
from app.core.models import ApprovalRequest, DesignRequest
from app.core.permissions import PermissionPolicy
from app.services.llm import LLMProvider
from app.services.memory import ProjectMemory
from app.services.orchestrator import Orchestrator

app = FastAPI(
    title="Design Intelligence System",
    version="0.3.0",
    description="A modular design intelligence API with read-only GitHub repository inspection.",
)
app.include_router(repositories_router)
memory = ProjectMemory()
llm = LLMProvider()
orchestrator = Orchestrator(memory=memory, llm=llm)
policy = PermissionPolicy()


@app.get("/health")
def health():
    return {"status": "ok", "service": "design-intelligence-system", "version": app.version}


@app.get("/api/v1/agents")
def list_agents():
    return [
        {"role": role.value, "description": agent.description}
        for role, agent in orchestrator.registry.items()
    ]


@app.get("/api/v1/provider")
def provider_status():
    """Expose safe provider metadata only; never return credentials."""
    return {
        "configured": llm.enabled,
        "provider": llm.provider if llm.enabled else None,
        "model": llm.model if llm.enabled else None,
        "mode": "llm" if llm.enabled else "deterministic",
    }


@app.post("/api/v1/design/runs")
def create_design_run(request: DesignRequest):
    return orchestrator.run(request).model_dump(mode="json")


@app.post("/api/v1/permissions/evaluate")
def evaluate_permission(request: ApprovalRequest):
    return policy.evaluate(request).model_dump()
