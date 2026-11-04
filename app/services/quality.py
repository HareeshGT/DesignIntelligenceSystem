from typing import Any


QUALITY_WEIGHTS = {
    "visual_design": 20,
    "ux_usability": 20,
    "typography_composition": 15,
    "design_consistency": 15,
    "originality": 10,
    "functional_implementation": 10,
    "responsiveness": 5,
    "accessibility": 5,
}


def evaluate_quality(scores: dict[str, float] | None = None,
                     critical_issues: list[str] | None = None) -> dict[str, Any]:
    """Score only supplied evidence; absent measurements remain explicitly unverified."""
    scores = scores or {}
    critical_issues = critical_issues or []
    valid = {k: max(0.0, min(100.0, float(v))) for k, v in scores.items() if k in QUALITY_WEIGHTS}
    total_weight = sum(QUALITY_WEIGHTS[k] for k in valid)
    weighted = (sum(valid[k] * QUALITY_WEIGHTS[k] for k in valid) / total_weight
                if total_weight else None)
    return {
        "weighted_score": round(weighted, 2) if weighted is not None else None,
        "measured_categories": sorted(valid),
        "unverified_categories": sorted(set(QUALITY_WEIGHTS) - set(valid)),
        "weights": QUALITY_WEIGHTS,
        "critical_issues": critical_issues,
        "release_gate": "blocked" if critical_issues else "not_verified",
        "note": "A score is not a release approval; browser and functional evidence are required.",
    }
