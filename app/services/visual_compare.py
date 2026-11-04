from __future__ import annotations

import base64
import io

from PIL import Image, ImageChops, ImageStat

from app.core.visual_comparison_models import VisualComparisonRequest
from app.core.visual_models import VisualInspectionRequest
from app.services.visual_inspector import VisualInspector


class VisualComparisonError(RuntimeError):
    pass


class VisualComparator:
    def compare(self, request: VisualComparisonRequest) -> dict:
        inspector = VisualInspector()
        baseline = inspector.inspect(VisualInspectionRequest(
            url=request.baseline_url, capture_screenshots=True, analyze_with_vision=False,
            page_timeout_ms=request.page_timeout_ms,
        ))
        candidate = inspector.inspect(VisualInspectionRequest(
            url=request.candidate_url, capture_screenshots=True, analyze_with_vision=False,
            page_timeout_ms=request.page_timeout_ms,
        ))
        before = {item.name: item for item in baseline.viewports}
        after = {item.name: item for item in candidate.viewports}
        comparisons = []
        for name in ("desktop", "tablet", "mobile"):
            left, right = before.get(name), after.get(name)
            if not left or not right or not left.screenshot_base64 or not right.screenshot_base64:
                continue
            try:
                image_a = Image.open(io.BytesIO(base64.b64decode(left.screenshot_base64))).convert("RGB")
                image_b = Image.open(io.BytesIO(base64.b64decode(right.screenshot_base64))).convert("RGB")
                if image_a.size != image_b.size:
                    image_b = image_b.resize(image_a.size)
                difference = ImageChops.difference(image_a, image_b)
                mean_error = sum(ImageStat.Stat(difference).mean) / 3
                similarity = round(max(0.0, 100.0 * (1.0 - mean_error / 255.0)), 2)
                changed_pixels = sum(difference.convert("L").histogram()[19:])
                total_pixels = image_a.width * image_a.height
                comparisons.append({
                    "viewport": name, "width": image_a.width, "height": image_a.height,
                    "pixel_similarity_percent": similarity,
                    "changed_pixel_percent": round(100.0 * changed_pixels / total_pixels, 2),
                    "baseline_screenshot_base64": left.screenshot_base64,
                    "candidate_screenshot_base64": right.screenshot_base64,
                })
            except (ValueError, OSError) as exc:
                raise VisualComparisonError("Could not decode screenshots for visual comparison.") from exc
        before_titles = {item.title for item in baseline.findings}
        after_titles = {item.title for item in candidate.findings}
        return {
            "baseline_url": baseline.inspected_url, "candidate_url": candidate.inspected_url,
            "comparisons": comparisons,
            "baseline_score": baseline.score, "candidate_score": candidate.score,
            "score_delta": candidate.score - baseline.score,
            "resolved_finding_titles": sorted(before_titles - after_titles),
            "new_finding_titles": sorted(after_titles - before_titles),
            "baseline_findings": [item.model_dump() for item in baseline.findings],
            "candidate_findings": [item.model_dump() for item in candidate.findings],
            "limitations": [
                "Pixel similarity measures visual change, not whether the change is aesthetically better.",
                "Both URLs are inspected independently; dynamic content, animation and personalized data can affect comparison.",
                "Use the finding delta and human review alongside screenshot similarity.",
            ],
        }
