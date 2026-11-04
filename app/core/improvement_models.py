from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Limits are shared with the dashboard clients. studio.js and app.js send the
# specialist handoff / visual summary truncated to MAX_VISUAL_SUMMARY_CHARS, so
# the API must accept at least that much. Over-long free text is trimmed rather
# than rejected: it is model *context*, and a 422 here only blocks the user.
MAX_VISUAL_SUMMARY_CHARS = 10_000
# Absolute ceiling so a hostile caller cannot post an unbounded body.
HARD_MAX_TEXT_CHARS = 100_000

FINDING_LIMITS = {
    "category": 80,
    "title": 180,
    "description": 600,
    "evidence": 600,
    "recommendation": 600,
}
FINDING_FALLBACKS = {
    "category": "general",
    "title": "Untitled finding",
    "description": "No description provided.",
    "evidence": "No evidence provided.",
    "recommendation": "Review and improve this area.",
}
SEVERITIES = {"high", "medium", "low"}


def _truncate(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


class ImprovementFinding(BaseModel):
    category: str = Field(min_length=1, max_length=FINDING_LIMITS["category"])
    severity: Literal["high", "medium", "low"]
    title: str = Field(min_length=1, max_length=FINDING_LIMITS["title"])
    description: str = Field(min_length=1, max_length=FINDING_LIMITS["description"])
    evidence: str = Field(min_length=1, max_length=FINDING_LIMITS["evidence"])
    recommendation: str = Field(min_length=1, max_length=FINDING_LIMITS["recommendation"])

    @model_validator(mode="before")
    @classmethod
    def normalize_finding(cls, data: Any):
        """Fit findings from visual inspectors/LLMs to the bounds below.

        ``VisualFinding`` has unbounded strings and the vision model can emit
        any severity, so strict bounds here used to turn a normal audit into a
        422 ("string_too_long" / "string_too_short" / "literal_error").
        """
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        for key, limit in FINDING_LIMITS.items():
            raw = normalized.get(key)
            text = raw.strip() if isinstance(raw, str) else ("" if raw is None else str(raw).strip())
            normalized[key] = _truncate(text, limit) if text else FINDING_FALLBACKS[key]
        severity = str(normalized.get("severity", "")).strip().lower()
        normalized["severity"] = severity if severity in SEVERITIES else "medium"
        return normalized


class ImprovementProposalRequest(BaseModel):
    repository: str = Field(min_length=3, max_length=200)
    ref: str | None = Field(default=None, min_length=1, max_length=250)
    branch_name: str | None = Field(default=None, min_length=1, max_length=120)
    design_brief: str = Field(default="", max_length=10000)
    target_files: list[str] = Field(min_length=1, max_length=4)
    # A visual audit can legitimately produce zero findings. The visual summary or
    # design brief still gives the model grounded context for a proposal.
    findings: list[ImprovementFinding] = Field(default_factory=list, max_length=20)
    # Preserve the coordinated specialist handoff. Longer text is trimmed to
    # MAX_VISUAL_SUMMARY_CHARS instead of failing validation.
    visual_summary: str = Field(default="", max_length=MAX_VISUAL_SUMMARY_CHARS)
    source_sharing_consent: Literal[True]

    @field_validator("visual_summary", mode="before")
    @classmethod
    def bound_visual_summary(cls, value: Any):
        if value is None:
            return ""
        if not isinstance(value, str):
            return value
        if len(value) > HARD_MAX_TEXT_CHARS:
            raise ValueError(f"visual_summary must be at most {HARD_MAX_TEXT_CHARS} characters.")
        return _truncate(value, MAX_VISUAL_SUMMARY_CHARS) if len(value) > MAX_VISUAL_SUMMARY_CHARS else value

    @model_validator(mode="after")
    def require_design_context(self):
        if not self.findings and not self.visual_summary.strip() and not self.design_brief.strip():
            raise ValueError("Provide at least one visual finding, a visual summary, or a design brief.")
        return self


class ImprovementApplyRequest(BaseModel):
    proposal_token: str = Field(min_length=20, max_length=500000)
    approval: bool
