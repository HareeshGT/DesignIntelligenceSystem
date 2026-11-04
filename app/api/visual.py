import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app.core.visual_models import VisualInspectionRequest
from app.core.visual_comparison_models import VisualComparisonRequest
from app.services.visual_compare import VisualComparator, VisualComparisonError
from app.services.visual_inspector import VisualInspectionError, VisualInspector

router = APIRouter(prefix="/api/v1/visual", tags=["visual intelligence"])


def _api_key_matches(api_key: str | None, expected_key: str) -> bool:
    return bool(api_key) and hmac.compare_digest(api_key.encode("utf-8"), expected_key.encode("utf-8"))


@router.post("/inspect")
def inspect_visual(
    request: VisualInspectionRequest,
    api_key: str | None = Header(default=None, alias="X-DIS-API-Key"),
):
    """Render a public web page at desktop, tablet and mobile sizes and audit observable UI signals."""
    expected_key = os.getenv("DIS_REPOSITORY_INSPECTION_API_KEY", "").strip()
    credentials_configured = bool(os.getenv("DIS_GITHUB_TOKEN", "").strip() or os.getenv("DIS_GITHUB_WRITE_TOKEN", "").strip() or os.getenv("DIS_LLM_API_KEY", "").strip() or os.getenv("DIS_VISION_LLM_API_KEY", "").strip())
    if credentials_configured and not expected_key:
        raise HTTPException(status_code=503, detail="Inspection credentials are configured; set DIS_REPOSITORY_INSPECTION_API_KEY.")
    if expected_key and (
        not _api_key_matches(api_key, expected_key)
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing DIS API key.")
    try:
        return VisualInspector().inspect(request).model_dump(mode="json")
    except VisualInspectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/compare")
def compare_visuals(
    request: VisualComparisonRequest,
    api_key: str | None = Header(default=None, alias="X-DIS-API-Key"),
):
    """Compare before/after public application screenshots and deterministic findings."""
    expected_key = os.getenv("DIS_REPOSITORY_INSPECTION_API_KEY", "").strip()
    credentials_configured = bool(os.getenv("DIS_GITHUB_TOKEN", "").strip() or os.getenv("DIS_GITHUB_WRITE_TOKEN", "").strip() or os.getenv("DIS_LLM_API_KEY", "").strip() or os.getenv("DIS_VISION_LLM_API_KEY", "").strip())
    if credentials_configured and not expected_key:
        raise HTTPException(status_code=503, detail="Set DIS_REPOSITORY_INSPECTION_API_KEY.")
    if expected_key and (not api_key or not hmac.compare_digest(api_key, expected_key)):
        raise HTTPException(status_code=401, detail="Invalid or missing DIS API key.")
    try:
        return VisualComparator().compare(request)
    except (VisualComparisonError, VisualInspectionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
