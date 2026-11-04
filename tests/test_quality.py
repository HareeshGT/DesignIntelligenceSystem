from app.services.quality import evaluate_quality


def test_quality_score_uses_only_measured_categories():
    result = evaluate_quality({"visual_design": 80, "accessibility": 100})
    assert result["weighted_score"] == 84.0
    assert "ux_usability" in result["unverified_categories"]
    assert result["release_gate"] == "not_verified"


def test_critical_issues_block_release_gate():
    result = evaluate_quality({"visual_design": 100}, ["Primary action is unusable"])
    assert result["release_gate"] == "blocked"
