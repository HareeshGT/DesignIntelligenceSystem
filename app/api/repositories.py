from fastapi import APIRouter, HTTPException

from app.core.repository_models import RepositoryInspectionRequest
from app.services.github_repository import GitHubRepositoryInspector, RepositoryInspectionError
from app.services.llm import LLMProvider

router = APIRouter(prefix="/api/v1/repositories", tags=["repositories"])


@router.post("/inspect")
def inspect_repository(request: RepositoryInspectionRequest):
    """Inspect GitHub metadata and a bounded set of files without executing repository code."""
    try:
        result = GitHubRepositoryInspector(llm=LLMProvider()).inspect(
            repository=request.repository,
            ref=request.ref,
            include_file_samples=request.include_file_samples,
        )
        return result.model_dump(mode="json")
    except RepositoryInspectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
