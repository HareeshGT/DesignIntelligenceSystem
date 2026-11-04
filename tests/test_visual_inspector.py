from app.core.visual_models import VisualInspectionRequest
from app.services.visual_inspector import (
    VisualInspectionError,
    _findings,
    _score,
    _validate_public_url,
)


def test_rejects_non_http_urls():
    try:
        _validate_public_url("file:///etc/passwd")
    except VisualInspectionError:
        pass
    else:
        raise AssertionError("file URLs must be rejected")


def test_rejects_localhost():
    try:
        _validate_public_url("http://localhost:8000")
    except VisualInspectionError:
        pass
    else:
        raise AssertionError("localhost must be rejected")


def test_rejects_private_ip():
    try:
        _validate_public_url("http://127.0.0.1:8000")
    except VisualInspectionError:
        pass
    else:
        raise AssertionError("loopback addresses must be rejected")


def test_request_defaults_to_three_viewports_capture():
    request = VisualInspectionRequest(url="https://example.com")
    assert request.capture_screenshots is True
    assert request.page_timeout_ms == 20000


def test_detects_horizontal_overflow_and_accessibility_issues():
    metrics = {
        "horizontal_overflow": True, "document_width": 500, "viewport_width": 390,
        "images_missing_alt": 1, "visible_images": 2, "buttons_without_name": 1,
        "visible_buttons": 3, "links_without_name": 0, "visible_links": 2,
        "inputs_without_label": 1, "visible_inputs": 2, "h1_count": 0,
        "text_characters": 500,
    }
    findings = _findings(metrics, "mobile")
    categories = {finding.category for finding in findings}
    assert {"responsive_design", "accessibility", "content_hierarchy"} <= categories
    score, grade = _score(findings)
    assert 0 <= score < 100
    assert grade in {"A", "B", "C", "D", "F"}


def test_score_is_perfect_without_findings():
    assert _score([]) == (100, "A")
