from app.core.improvement_models import ImprovementProposalRequest


def test_improvement_proposal_accepts_multi_specialist_visual_summary():
    summary = "\n".join(
        f"{role}: Evaluate the product-specific design direction, hierarchy, "
        "accessibility, reusable components, responsive behavior, and visual quality."
        for role in (
            "Creative Director",
            "UX Architect",
            "Visual Designer",
            "Design Systems Engineer",
            "Frontend Engineer",
            "Visual QA Engineer",
            "Design Director",
        )
    )
    assert len(summary) > 1600

    request = ImprovementProposalRequest(
        repository="HareeshGT/NeighbourCommunityForum",
        ref="main",
        branch_name="dis/redesign",
        design_brief="Review opportunities for UI improvements.",
        target_files=[
            "frontend/src/App.css",
            "frontend/src/App.jsx",
            "frontend/src/index.css",
            "frontend/src/main.jsx",
        ],
        findings=[],
        visual_summary=summary,
        source_sharing_consent=True,
    )

    assert request.visual_summary == summary


def test_improvement_proposal_still_bounds_visual_summary_length():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ImprovementProposalRequest(
            repository="owner/repo",
            target_files=["src/App.jsx"],
            design_brief="Improve the UI.",
            visual_summary="x" * 6001,
            source_sharing_consent=True,
        )
