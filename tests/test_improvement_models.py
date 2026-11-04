import pytest
from pydantic import ValidationError

from app.core.improvement_models import (
    HARD_MAX_TEXT_CHARS,
    MAX_VISUAL_SUMMARY_CHARS,
    ImprovementFinding,
    ImprovementProposalRequest,
)

ROLES = (
    "Creative Director",
    "UX Architect",
    "Visual Designer",
    "Design Systems Engineer",
    "Frontend Engineer",
    "Visual QA Engineer",
    "Design Director",
)


def _request(**overrides):
    payload = dict(
        repository="HareeshGT/NeighbourCommunityForum",
        ref="main",
        branch_name="dis/redesign",
        design_brief="Review opportunities for UI improvements.",
        target_files=["frontend/src/App.css", "frontend/src/App.jsx"],
        findings=[],
        visual_summary="",
        source_sharing_consent=True,
    )
    payload.update(overrides)
    return ImprovementProposalRequest(**payload)


def _specialist_summary(sentences_per_role: int) -> str:
    body = (
        "Evaluate the product-specific design direction, hierarchy, accessibility, "
        "reusable components, responsive behavior, and visual quality. "
    ) * sentences_per_role
    return "\n".join(f"{role}: {body.strip()}" for role in ROLES)


def test_realistic_multi_specialist_summary_beyond_old_limits_is_accepted():
    # ~7.7k characters: above the old 1600 and 6000 limits that caused repeated 422s,
    # and within the 10000 characters the Studio client sends.
    summary = _specialist_summary(8)
    assert 6000 < len(summary) <= MAX_VISUAL_SUMMARY_CHARS

    assert _request(visual_summary=summary).visual_summary == summary


def test_client_sized_summary_is_never_rejected_for_length():
    # studio.js slices the specialist context to exactly 10000 characters.
    assert len(_request(visual_summary="x" * 10_000).visual_summary) == 10_000


def test_overlong_summary_is_trimmed_not_rejected():
    request = _request(visual_summary="x" * 25_000)
    assert len(request.visual_summary) == MAX_VISUAL_SUMMARY_CHARS


def test_absurdly_large_summary_is_still_rejected():
    with pytest.raises(ValidationError):
        _request(visual_summary="x" * (HARD_MAX_TEXT_CHARS + 1))


def test_long_empty_or_odd_findings_are_normalized_instead_of_rejected():
    request = _request(
        findings=[
            {
                "category": "c" * 200,
                "severity": "Critical",
                "title": "t" * 500,
                "description": "d" * 5000,
                "evidence": "",
                "recommendation": "  ",
            }
        ]
    )
    finding = request.findings[0]
    assert len(finding.category) <= 80
    assert len(finding.title) <= 180
    assert len(finding.description) <= 600
    assert finding.severity == "medium"
    assert finding.evidence and finding.recommendation


def test_valid_finding_is_unchanged_apart_from_whitespace():
    finding = ImprovementFinding(
        category="accessibility",
        severity="HIGH",
        title="Missing labels",
        description="Inputs lack labels.",
        evidence="3 of 4 inputs unlabeled.",
        recommendation="Add <label> elements.",
    )
    assert finding.severity == "high"
    assert finding.title == "Missing labels"


def test_proposal_still_requires_some_design_context():
    with pytest.raises(ValidationError):
        _request(design_brief="", visual_summary="", findings=[])
