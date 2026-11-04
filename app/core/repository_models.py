from pydantic import BaseModel, Field


class RepositoryInspectionRequest(BaseModel):
    repository: str = Field(
        min_length=3,
        max_length=200,
        description="GitHub repository in owner/name format or a github.com URL.",
    )
    ref: str | None = Field(default=None, min_length=1, max_length=250)
    include_file_samples: bool = True


class RepositoryFileEvidence(BaseModel):
    path: str
    category: str
    bytes_read: int
    truncated: bool = False


class RepositoryInspection(BaseModel):
    repository: str
    ref: str
    default_branch: str | None = None
    description: str | None = None
    primary_language: str | None = None
    detected_stacks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    platform_profiles: list[dict] = Field(default_factory=list)
    app_entry_points: list[str] = Field(default_factory=list)
    route_and_page_files: list[str] = Field(default_factory=list)
    component_and_style_files: list[str] = Field(default_factory=list)
    design_system_evidence: list[str] = Field(default_factory=list)
    test_and_lint_commands: list[str] = Field(default_factory=list)
    repository_signals: list[str] = Field(default_factory=list)
    file_evidence: list[RepositoryFileEvidence] = Field(default_factory=list)
    architecture_summary: str
    limitations: list[str] = Field(default_factory=list)
    inspected_file_count: int = 0
    tree_entry_count: int = 0
