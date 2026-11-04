from pydantic import BaseModel, Field

class ImprovementProposalRequest(BaseModel):
    repository: str = Field(min_length=3, max_length=200)
    ref: str | None = Field(default=None, min_length=1, max_length=250)
    target_files: list[str] = Field(min_length=1, max_length=4)
    findings: list[dict] = Field(min_length=1, max_length=20)
    visual_summary: str = Field(default="", max_length=1600)

class ImprovementApplyRequest(BaseModel):
    proposal_token: str = Field(min_length=20, max_length=500000)
    approval: bool
