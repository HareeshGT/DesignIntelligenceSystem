import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app.core.improvement_models import ImprovementApplyRequest, ImprovementProposalRequest
from app.services.improvements import ImprovementError, ImprovementService

router = APIRouter(prefix="/api/v1/improvements", tags=["UI improvements"])

def _authorize(api_key: str | None) -> None:
    expected = os.getenv("DIS_REPOSITORY_INSPECTION_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Set DIS_REPOSITORY_INSPECTION_API_KEY before using improvement endpoints.")
    if not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing DIS API key.")

@router.post("/propose")
def propose_improvement(request: ImprovementProposalRequest, api_key: str | None = Header(default=None, alias="X-DIS-API-Key")):
    """Generate a bounded UI source patch. This endpoint never writes to GitHub."""
    _authorize(api_key)
    try:
        return ImprovementService().propose(request)
    except ImprovementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/apply")
def apply_improvement(request: ImprovementApplyRequest, api_key: str | None = Header(default=None, alias="X-DIS-API-Key")):
    """Create a GitHub PR from a signed proposal after explicit user approval."""
    _authorize(api_key)
    try:
        return ImprovementService().apply(request.proposal_token, request.approval)
    except ImprovementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
