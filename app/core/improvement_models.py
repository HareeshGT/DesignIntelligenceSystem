from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
    branch_name: str | None = Field(default=None, min_length=1, max_length=120)
    design_brief: str = Field(default="", max_length=10000)
    target_files: list[str] = Field(min_length=1, max_length=4)
    # A visual audit can legitimately produce zero findings. The visual summary or
    # design brief still gives the model grounded context for a proposal.
    findings: list[ImprovementFinding] = Field(default_factory=list, max_length=20)
    visual_summary: str = Field(default="", max_length=1600)
    source_sharing_consent: Literal[True]

    @model_validator(mode="after")
    def require_design_context(self):
        if not self.findings and not self.visual_summary.strip() and not self.design_brief.strip():
            raise ValueError("Provide at least one visual finding, a visual summary, or a design brief.")
        return self


class ImprovementApplyRequest(BaseModel):
    proposal_token: str = Field(min_length=20, max_length=500000)
    approval: bool
