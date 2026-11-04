from typing import Literal

from pydantic import BaseModel, Field

class ImprovementFinding(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    severity: Literal["high", "medium", "low"]
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(min_length=1, max_length=600)
    evidence: str = Field(min_length=1, max_length=600)
    recommendation: str = Field(min_length=1, max_length=600)


class ImprovementProposalRequest(BaseModel):
    repository: str = Field(min_length=3, max_length=200)
    ref: str | None = Field(default=None, min_length=1, max_length=250)
    target_files: list[str] = Field(min_length=1, max_length=4)
    findings: list[ImprovementFinding] = Field(min_length=1, max_length=20)
    visual_summary: str = Field(default="", max_length=1600)
    source_sharing_consent: Literal[True]

class ImprovementApplyRequest(BaseModel):
    proposal_token: str = Field(min_length=20, max_length=500000)
    approval: bool
