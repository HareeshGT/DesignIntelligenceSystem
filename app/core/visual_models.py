from pydantic import BaseModel, Field, HttpUrl


class VisualInspectionRequest(BaseModel):
    url: HttpUrl
    capture_screenshots: bool = True
    page_timeout_ms: int = Field(default=20000, ge=3000, le=60000)


class ViewportEvidence(BaseModel):
    name: str
    width: int
    height: int
    screenshot_base64: str | None = None


class VisualFinding(BaseModel):
    category: str
    severity: str
    title: str
    description: str
    evidence: str
    recommendation: str


class VisualInspectionResponse(BaseModel):
    inspected_url: str
    page_title: str
    final_url: str
    status_code: int | None = None
    score: int
    grade: str
    findings: list[VisualFinding] = Field(default_factory=list)
    metrics: dict[str, int | float | bool | str] = Field(default_factory=dict)
    viewports: list[ViewportEvidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    analysis_mode: str = "deterministic_dom_and_layout"
