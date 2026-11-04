import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app.core.repository_models import RepositoryInspectionRequest
from app.services.github_repository import GitHubRepositoryInspector, RepositoryInspectionError
from app.services.llm import request_llm

router = APIRouter(prefix="/api/v1/repositories", tags=["repositories"])


@router.post("/inspect")
def inspect_repository(
    request: RepositoryInspectionRequest,
    api_key: str | None = Header(default=None, alias="X-DIS-API-Key"),
    llm_provider: str | None = Header(default=None, alias="X-DIS-LLM-Provider"),
    llm_model: str | None = Header(default=None, alias="X-DIS-LLM-Model"),
    llm_api_key: str | None = Header(default=None, alias="X-DIS-LLM-API-Key"),
    llm_base_url: str | None = Header(default=None, alias="X-DIS-LLM-Base-URL"),
    github_token: str | None = Header(default=None, alias="X-DIS-GITHUB-READ-TOKEN"),
):
    """Inspect GitHub metadata and bounded file samples without executing repository code."""
    llm = request_llm(llm_provider, llm_model, llm_api_key, llm_base_url)
    expected_key = os.getenv("DIS_REPOSITORY_INSPECTION_API_KEY", "").strip()
    # Browser-supplied GitHub/model credentials belong to this request. Require
    # shared DIS authentication only when the server itself holds credentials.
    server_credentials = bool(
        os.getenv("DIS_GITHUB_TOKEN", "").strip()
        or os.getenv("DIS_GITHUB_WRITE_TOKEN", "").strip()
        or os.getenv("DIS_LLM_API_KEY", "").strip()
    )

    # Fail closed rather than silently exposing server-held credentials.
    if server_credentials and not expected_key:
        raise HTTPException(
            status_code=503,
            detail="Server-side credentials are configured but DIS_REPOSITORY_INSPECTION_API_KEY is missing from this running service.",
        )
    if expected_key and (
        not api_key or not hmac.compare_digest(api_key, expected_key)
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing repository inspection API key.")

    try:
        result = GitHubRepositoryInspector(llm=llm, token=github_token).inspect(
            repository=request.repository,
            ref=request.ref,
            include_file_samples=request.include_file_samples,
        )
        return result.model_dump(mode="json")
    except RepositoryInspectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
