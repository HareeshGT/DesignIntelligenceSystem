from pydantic import BaseModel, Field, HttpUrl


class VisualInspectionRequest(BaseModel):
    url: HttpUrl
    capture_screenshots: bool = True
    page_timeout_ms: int = Field(default=20000, ge=3000, le=60000)
    analyze_with_vision: bool = True
    crawl_internal_routes: bool = False
    max_routes: int = Field(default=4, ge=1, le=8)
    analyze_with_vision: bool = True


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


class InspectedPage(BaseModel):
    url: str
    title: str = ""
    status_code: int | None = None
    viewport: str = "desktop"


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
    inspected_pages: list[InspectedPage] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    visual_summary: str = ""
    design_observations: list[str] = Field(default_factory=list)
    design_system_signals: dict[str, list[str]] = Field(default_factory=dict)
    analysis_mode: str = "deterministic_dom_and_layout"
