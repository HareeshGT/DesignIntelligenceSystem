import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app.core.improvement_models import ImprovementApplyRequest, ImprovementProposalRequest
from app.services.improvements import ImprovementError, ImprovementService
from app.services.llm import request_llm

router = APIRouter(prefix="/api/v1/improvements", tags=["UI improvements"])

def _authorize(api_key: str | None) -> None:
    expected = os.getenv("DIS_REPOSITORY_INSPECTION_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Set DIS_REPOSITORY_INSPECTION_API_KEY before using improvement endpoints.")
    if not api_key or not hmac.compare_digest(api_key.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid or missing DIS API key.")

@router.post("/propose")
def propose_improvement(request: ImprovementProposalRequest, api_key: str | None = Header(default=None, alias="X-DIS-API-Key"), llm_provider: str | None = Header(default=None, alias="X-DIS-LLM-Provider"), llm_model: str | None = Header(default=None, alias="X-DIS-LLM-Model"), llm_api_key: str | None = Header(default=None, alias="X-DIS-LLM-API-Key"), llm_base_url: str | None = Header(default=None, alias="X-DIS-LLM-Base-URL"), github_read_token: str | None = Header(default=None, alias="X-DIS-GITHUB-READ-TOKEN"), github_write_token: str | None = Header(default=None, alias="X-DIS-GITHUB-WRITE-TOKEN")):
    """Generate a bounded UI source patch. This endpoint never writes to GitHub."""
    _authorize(api_key)
    try:
        return ImprovementService(request_llm(llm_provider, llm_model, llm_api_key, llm_base_url), github_read_token, github_write_token).propose(request)
    except ImprovementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/apply")
def apply_improvement(request: ImprovementApplyRequest, api_key: str | None = Header(default=None, alias="X-DIS-API-Key"), github_write_token: str | None = Header(default=None, alias="X-DIS-GITHUB-WRITE-TOKEN")):
    """Create a GitHub PR from a signed proposal after explicit user approval."""
    _authorize(api_key)
    try:
        return ImprovementService(write_token=github_write_token).apply(request.proposal_token, request.approval)
    except ImprovementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
