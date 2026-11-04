from fastapi import FastAPI
from app.core.models import ApprovalRequest, DesignRequest
from app.core.permissions import PermissionPolicy
from app.services.memory import ProjectMemory
from app.services.orchestrator import Orchestrator

app = FastAPI(
    title="Design Intelligence System",
    version="0.1.0",
    description="A modular multi-agent design planning and quality intelligence API.",
)
memory = ProjectMemory()
orchestrator = Orchestrator(memory=memory)
policy = PermissionPolicy()


@app.get("/health")
def health():
    return {"status": "ok", "service": "design-intelligence-system", "version": app.version}


@app.get("/api/v1/agents")
def list_agents():
    return [{"role": role.value, "description": agent.description}
            for role, agent in orchestrator.registry.items()]


@app.post("/api/v1/design/runs")
def create_design_run(request: DesignRequest):
    return orchestrator.run(request).model_dump(mode="json")


@app.post("/api/v1/permissions/evaluate")
def evaluate_permission(request: ApprovalRequest):
    return policy.evaluate(request).model_dump()
