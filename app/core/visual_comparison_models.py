from pydantic import BaseModel, Field, HttpUrl

class VisualComparisonRequest(BaseModel):
    baseline_url: HttpUrl
    candidate_url: HttpUrl
    page_timeout_ms: int = Field(default=20000, ge=3000, le=60000)
