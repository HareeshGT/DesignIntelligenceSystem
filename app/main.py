import hmac
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.repositories import router as repositories_router
from app.api.visual import router as visual_router
from app.api.improvements import router as improvements_router
from app.core.models import ApprovalRequest, DesignRequest
from app.core.permissions import PermissionPolicy
from app.services.llm import LLMProvider
from app.services.visual_design import VisualDesignAnalyzer
from app.services.memory import ProjectMemory
from app.services.orchestrator import Orchestrator

# Load local development configuration before constructing provider clients.
load_dotenv()

app = FastAPI(
    title="Design Intelligence System",
    version="0.4.0",
    description="A modular design intelligence API with repository and browser-based visual inspection.",
)
app.include_router(repositories_router)
app.include_router(visual_router)
app.include_router(improvements_router)
WEB_STATIC_DIR = Path(__file__).parent / "web" / "static"
app.mount("/static", StaticFiles(directory=WEB_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    """Serve the browser-based DIS workspace."""
    return FileResponse(WEB_STATIC_DIR / "index.html")


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
    vision_provider = VisualDesignAnalyzer().provider
    return {
        "configured": llm.enabled,
        "provider": llm.provider if llm.enabled else None,
        "model": llm.model if llm.enabled else None,
        "mode": "llm" if llm.enabled else "deterministic",
        "vision_configured": vision_provider.enabled,
        "vision_provider": vision_provider.provider if vision_provider.enabled else None,
        "vision_model": vision_provider.model if vision_provider.enabled else None,
    }


@app.post("/api/v1/design/runs")
def create_design_run(request: DesignRequest, api_key: str | None = Header(default=None, alias="X-DIS-API-Key")):
    """Run the specialist design team behind the same shared-key boundary as repository analysis."""
    expected_key = os.getenv("DIS_REPOSITORY_INSPECTION_API_KEY", "").strip()
    sensitive_credentials = bool(os.getenv("DIS_GITHUB_TOKEN", "").strip() or os.getenv("DIS_GITHUB_WRITE_TOKEN", "").strip() or llm.enabled)
    if sensitive_credentials and not expected_key:
        raise HTTPException(status_code=503, detail="Set DIS_REPOSITORY_INSPECTION_API_KEY before using AI design runs.")
    if expected_key and (not api_key or not hmac.compare_digest(api_key.encode("utf-8"), expected_key.encode("utf-8"))):
        raise HTTPException(status_code=401, detail="Invalid or missing DIS API key.")
    return orchestrator.run(request).model_dump(mode="json")


@app.post("/api/v1/permissions/evaluate")
def evaluate_permission(request: ApprovalRequest):
    return policy.evaluate(request).model_dump()
