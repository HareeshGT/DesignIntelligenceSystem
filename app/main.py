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
from app.services.llm import LLMProvider, request_llm
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
def provider_status(llm_provider: str | None = Header(default=None, alias="X-DIS-LLM-Provider"), llm_model: str | None = Header(default=None, alias="X-DIS-LLM-Model"), llm_api_key: str | None = Header(default=None, alias="X-DIS-LLM-API-Key"), llm_base_url: str | None = Header(default=None, alias="X-DIS-LLM-Base-URL")):
    """Expose safe request-scoped provider metadata only; never return credentials."""
    current_llm = request_llm(llm_provider, llm_model, llm_api_key, llm_base_url)
    vision_provider = VisualDesignAnalyzer(provider=current_llm).provider
    return {
        "configured": current_llm.enabled,
        "provider": current_llm.provider if current_llm.enabled else None,
        "model": current_llm.model if current_llm.enabled else None,
        "mode": "llm" if current_llm.enabled else "deterministic",
        "vision_configured": vision_provider.enabled,
        "vision_provider": vision_provider.provider if vision_provider.enabled else None,
        "vision_model": vision_provider.model if vision_provider.enabled else None,
    }


@app.post("/api/v1/design/runs")
def create_design_run(request: DesignRequest, api_key: str | None = Header(default=None, alias="X-DIS-API-Key"), llm_provider: str | None = Header(default=None, alias="X-DIS-LLM-Provider"), llm_model: str | None = Header(default=None, alias="X-DIS-LLM-Model"), llm_api_key: str | None = Header(default=None, alias="X-DIS-LLM-API-Key"), llm_base_url: str | None = Header(default=None, alias="X-DIS-LLM-Base-URL")):
    """Run specialists with request-scoped user provider credentials."""
    request_provider = request_llm(llm_provider, llm_model, llm_api_key, llm_base_url)
    expected_key = os.getenv("DIS_REPOSITORY_INSPECTION_API_KEY", "").strip()
    sensitive_credentials = bool(os.getenv("DIS_GITHUB_TOKEN", "").strip() or os.getenv("DIS_GITHUB_WRITE_TOKEN", "").strip() or request_provider.enabled)
    if sensitive_credentials and not expected_key:
        raise HTTPException(status_code=503, detail="Set DIS_REPOSITORY_INSPECTION_API_KEY before using AI design runs.")
    if expected_key and (not api_key or not hmac.compare_digest(api_key.encode("utf-8"), expected_key.encode("utf-8"))):
        raise HTTPException(status_code=401, detail="Invalid or missing DIS API key.")
    return Orchestrator(memory=memory, llm=request_provider).run(request).model_dump(mode="json")


@app.post("/api/v1/permissions/evaluate")
def evaluate_permission(request: ApprovalRequest):
    return policy.evaluate(request).model_dump()
