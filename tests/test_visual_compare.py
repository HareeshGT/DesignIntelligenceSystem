import base64
import io

from PIL import Image

from app.core.visual_comparison_models import VisualComparisonRequest
from app.core.visual_models import VisualInspectionResponse, ViewportEvidence
from app.services.visual_compare import VisualComparator


def _image(color):
    image = Image.new("RGB", (24, 24), color)
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return base64.b64encode(output.getvalue()).decode()


def test_comparator_reports_pixel_change_and_score_delta(monkeypatch):
    baseline = VisualInspectionResponse(
        inspected_url="https://before.example", page_title="Before", final_url="https://before.example",
        score=70, grade="C", findings=[],
        viewports=[ViewportEvidence(name="desktop", width=1440, height=1000, screenshot_base64=_image("white"))],
    )
    candidate = VisualInspectionResponse(
        inspected_url="https://after.example", page_title="After", final_url="https://after.example",
        score=85, grade="B", findings=[],
        viewports=[ViewportEvidence(name="desktop", width=1440, height=1000, screenshot_base64=_image("black"))],
    )
    class FakeInspector:
        def inspect(self, request):
            return baseline if str(request.url) == "https://before.example/" else candidate
    monkeypatch.setattr("app.services.visual_compare.VisualInspector", FakeInspector)
    result = VisualComparator().compare(VisualComparisonRequest(
        baseline_url="https://before.example", candidate_url="https://after.example"
    ))
    assert result["score_delta"] == 15
    assert result["comparisons"][0]["changed_pixel_percent"] > 0
