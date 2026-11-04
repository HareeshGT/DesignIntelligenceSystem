import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app.core.visual_models import VisualInspectionRequest
from app.services.visual_inspector import VisualInspectionError, VisualInspector

router = APIRouter(prefix="/api/v1/visual", tags=["visual intelligence"])


@router.post("/inspect")
def inspect_visual(
    request: VisualInspectionRequest,
    api_key: str | None = Header(default=None, alias="X-DIS-API-Key"),
):
    """Render a public web page at desktop, tablet and mobile sizes and audit observable UI signals."""
    expected_key = os.getenv("DIS_REPOSITORY_INSPECTION_API_KEY", "").strip()
    if expected_key and (
        not api_key or not hmac.compare_digest(api_key, expected_key)
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing DIS API key.")
    try:
        return VisualInspector().inspect(request).model_dump(mode="json")
    except VisualInspectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
