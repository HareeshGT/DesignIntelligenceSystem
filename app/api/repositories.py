import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app.core.repository_models import RepositoryInspectionRequest
from app.services.github_repository import GitHubRepositoryInspector, RepositoryInspectionError
from app.services.llm import LLMProvider

router = APIRouter(prefix="/api/v1/repositories", tags=["repositories"])


@router.post("/inspect")
def inspect_repository(
    request: RepositoryInspectionRequest,
    api_key: str | None = Header(default=None, alias="X-DIS-API-Key"),
):
    """Inspect GitHub metadata and bounded file samples without executing repository code."""
    llm = LLMProvider()
    expected_key = os.getenv("DIS_REPOSITORY_INSPECTION_API_KEY", "").strip()
    has_sensitive_credentials = bool(os.getenv("DIS_GITHUB_TOKEN", "").strip() or llm.enabled)

    # Fail closed if a token or paid model is configured but endpoint authentication is not.
    if has_sensitive_credentials and not expected_key:
        raise HTTPException(
            status_code=503,
            detail="Repository inspection credentials are configured; set DIS_REPOSITORY_INSPECTION_API_KEY.",
        )
    if expected_key and (
        not api_key or not hmac.compare_digest(api_key, expected_key)
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing repository inspection API key.")

    try:
        result = GitHubRepositoryInspector(llm=llm).inspect(
            repository=request.repository,
            ref=request.ref,
            include_file_samples=request.include_file_samples,
        )
        return result.model_dump(mode="json")
    except RepositoryInspectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
