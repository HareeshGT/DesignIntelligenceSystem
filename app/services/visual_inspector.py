from __future__ import annotations

import base64
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Browser, Error as PlaywrightError, sync_playwright

from app.services.llm import ProviderError
from app.services.visual_design import VisualDesignAnalyzer

from app.core.visual_models import (
    InspectedPage,
    ViewportEvidence,
    VisualFinding,
    VisualInspectionRequest,
    VisualInspectionResponse,
)


VIEWPORTS = [
    ("desktop", 1440, 1000),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
]


class VisualInspectionError(RuntimeError):
    """Safe, user-facing browser inspection error."""


def _validate_public_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise VisualInspectionError("Only public HTTP or HTTPS URLs can be inspected.")
    if parsed.username or parsed.password:
        raise VisualInspectionError("URLs containing embedded credentials are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise VisualInspectionError("Localhost and local network targets are not allowed.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            }
        except (OSError, ValueError) as exc:
            raise VisualInspectionError("The target hostname could not be resolved safely.") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise VisualInspectionError("Private, loopback, link-local and reserved network targets are blocked.")


def _safe_route(route) -> None:
    request_url = route.request.url
    if request_url.startswith(("data:", "blob:")):
        route.continue_()
        return
    try:
        _validate_public_url(request_url)
    except VisualInspectionError:
        route.abort("blockedbyclient")
        return
    route.continue_()


def _collect_metrics(page) -> dict:
    return page.evaluate("""() => {
      const visible = (el) => {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
      };
      const named = (el) => (el.getAttribute('aria-label') ||
        el.getAttribute('title') || el.innerText || el.value || '').trim();
      const images = [...document.images].filter(visible);
      const buttons = [...document.querySelectorAll('button,[role="button"]')].filter(visible);
      const links = [...document.querySelectorAll('a[href]')].filter(visible);
      const inputs = [...document.querySelectorAll('input,select,textarea')].filter(visible);
      const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible);
      const root = document.documentElement;
      const body = document.body;
      return {
        title: document.title || '',
        viewport_width: innerWidth,
        viewport_height: innerHeight,
        document_width: Math.max(root.scrollWidth, body ? body.scrollWidth : 0),
        document_height: Math.max(root.scrollHeight, body ? body.scrollHeight : 0),
        horizontal_overflow: Math.max(root.scrollWidth, body ? body.scrollWidth : 0) > innerWidth + 1,
        visible_images: images.length,
        images_missing_alt: images.filter(img => !img.hasAttribute('alt')).length,
        visible_buttons: buttons.length,
        buttons_without_name: buttons.filter(el => !named(el)).length,
        visible_links: links.length,
        links_without_name: links.filter(el => !named(el)).length,
        visible_inputs: inputs.length,
        inputs_without_label: inputs.filter(el => {
          const id = el.id;
          return !(id && document.querySelector('label[for="' + CSS.escape(id) + '"]')) &&
            !el.closest('label') && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby');
        }).length,
        heading_count: headings.length,
        h1_count: headings.filter(el => el.tagName === 'H1').length,
        landmark_count: document.querySelectorAll('main,nav,header,footer,aside,[role="main"],[role="navigation"]').length,
        text_characters: (body ? body.innerText : '').trim().length
      };
    }""")


def _findings(metrics: dict, viewport: str) -> list[VisualFinding]:
    findings: list[VisualFinding] = []
    if metrics["horizontal_overflow"]:
        findings.append(VisualFinding(
            category="responsive_design", severity="high",
            title=f"Horizontal overflow at {viewport} viewport",
            description="The document is wider than the visible viewport, which can force users to scroll sideways.",
            evidence=f"Document width {metrics['document_width']}px vs viewport width {metrics['viewport_width']}px.",
            recommendation="Inspect fixed-width containers, wide tables, grids and media. Use responsive sizing and intentional overflow regions.",
        ))
    if metrics["images_missing_alt"]:
        findings.append(VisualFinding(
            category="accessibility", severity="medium",
            title="Images missing alternative text",
            description="Some visible images do not expose an alt attribute to assistive technology.",
            evidence=f"{metrics['images_missing_alt']} of {metrics['visible_images']} visible images lack alt attributes.",
            recommendation="Add meaningful alt text to informative images and empty alt text to decorative images.",
        ))
    if metrics["buttons_without_name"]:
        findings.append(VisualFinding(
            category="accessibility", severity="high",
            title="Buttons without accessible names",
            description="Some visible buttons do not expose a usable accessible name.",
            evidence=f"{metrics['buttons_without_name']} of {metrics['visible_buttons']} visible buttons have no detected name.",
            recommendation="Provide visible button text or an appropriate aria-label for icon-only controls.",
        ))
    if metrics["links_without_name"]:
        findings.append(VisualFinding(
            category="accessibility", severity="medium",
            title="Links without accessible names",
            description="Some visible links have no detectable text or accessible name.",
            evidence=f"{metrics['links_without_name']} of {metrics['visible_links']} visible links have no detected name.",
            recommendation="Give each link descriptive text or an aria-label that explains its destination.",
        ))
    if metrics["inputs_without_label"]:
        findings.append(VisualFinding(
            category="accessibility", severity="high",
            title="Form controls without labels",
            description="Some visible form controls are not associated with a detectable accessible label.",
            evidence=f"{metrics['inputs_without_label']} of {metrics['visible_inputs']} visible controls have no detected label.",
            recommendation="Associate each control with a label element or aria-label/aria-labelledby.",
        ))
    if metrics["h1_count"] == 0 and metrics["text_characters"] > 0:
        findings.append(VisualFinding(
            category="content_hierarchy", severity="low",
            title="No visible primary heading detected",
            description="The page has content but no visible H1 heading was detected.",
            evidence="Visible H1 count: 0.",
            recommendation="Add a clear page-level heading and structure subsequent sections with ordered heading levels.",
        ))
    if metrics["visible_images"] == 0 and metrics["text_characters"] < 80:
        findings.append(VisualFinding(
            category="content", severity="low",
            title="Very little visible page content",
            description="The rendered page contains very little visible text or imagery.",
            evidence=f"Visible text characters: {metrics['text_characters']}; visible images: 0.",
            recommendation="Confirm the page loaded completely and that the intended route is being inspected.",
        ))
    return findings


def _score(findings: list[VisualFinding]) -> tuple[int, str]:
    deductions = {"high": 15, "medium": 8, "low": 3}
    score = max(0, 100 - sum(deductions[item.severity] for item in findings))
    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 55 else "F"
    return score, grade


class VisualInspector:
    """Captures public web pages and audits observable DOM/layout signals."""

    def inspect(self, request: VisualInspectionRequest) -> VisualInspectionResponse:
        target = str(request.url)
        _validate_public_url(target)
        viewports: list[ViewportEvidence] = []
        findings: list[VisualFinding] = []
        aggregate: dict[str, int | float | bool | str] = {}
        page_title = ""
        final_url = target
        status_code: int | None = None
        inspected_pages: list[InspectedPage] = []
        discovered_routes: list[str] = []

        try:
            with sync_playwright() as playwright:
                browser: Browser = playwright.chromium.launch(
                    headless=True,
                    chromium_sandbox=True,
                    args=["--disable-dev-shm-usage"],
                )
                try:
                    for name, width, height in VIEWPORTS:
                        context = browser.new_context(
                            viewport={"width": width, "height": height},
                            device_scale_factor=1,
                            service_workers="block",
                            accept_downloads=False,
                        )
                        page = context.new_page()
                        page.route("**/*", _safe_route)
                        try:
                            response = page.goto(
                                target, wait_until="domcontentloaded",
                                timeout=request.page_timeout_ms,
                            )
                            page.wait_for_timeout(700)
                            metrics = _collect_metrics(page)
                            page_title = str(metrics.get("title") or page_title)
                            final_url = page.url
                            if name == "desktop":
                                inspected_pages.append(InspectedPage(url=page.url, title=page_title, status_code=response.status if response else None))
                                if request.crawl_internal_routes:
                                    original = urlparse(target)
                                    hrefs = page.eval_on_selector_all("a[href]", "items => items.map(item => item.href)")[:100]
                                    for href in hrefs:
                                        candidate = urlparse(urljoin(page.url, href))
                                        if candidate.scheme != original.scheme or candidate.hostname != original.hostname or candidate.port != original.port:
                                            continue
                                        if candidate.path == original.path or any(word in candidate.path.lower() for word in ("logout", "signout", "delete", "remove", "unsubscribe", "checkout", "purchase")):
                                            continue
                                        route = candidate._replace(query="", fragment="").geturl()
                                        try:
                                            _validate_public_url(route)
                                        except VisualInspectionError:
                                            continue
                                        if route not in discovered_routes:
                                            discovered_routes.append(route)
                                        if len(discovered_routes) >= request.max_routes:
                                            break
                            status_code = response.status if response else status_code
                            findings.extend(_findings(metrics, name))
                            for key, value in metrics.items():
                                if isinstance(value, (int, float)) and not isinstance(value, bool):
                                    aggregate[key] = max(aggregate.get(key, 0), value)
                                elif key == "horizontal_overflow":
                                    aggregate[key] = bool(aggregate.get(key, False) or value)
                            screenshot = None
                            if request.capture_screenshots:
                                screenshot = base64.b64encode(
                                    page.screenshot(type="jpeg", quality=62, full_page=False, animations="disabled")
                                ).decode("ascii")
                            viewports.append(ViewportEvidence(
                                name=name, width=width, height=height,
                                screenshot_base64=screenshot,
                            ))
                        except PlaywrightError as exc:
                            raise VisualInspectionError(
                                f"Could not render the target page at the {name} viewport: {str(exc)[:240]}"
                            ) from exc
                        finally:
                            context.close()
                finally:
                    browser.close()
                if request.crawl_internal_routes and discovered_routes:
                    route_browser = playwright.chromium.launch(
                        headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
                    )
                    try:
                        for route_url in discovered_routes[:request.max_routes]:
                            route_context = route_browser.new_context(
                                viewport={"width": 1440, "height": 1000},
                                service_workers="block", accept_downloads=False,
                            )
                            route_page = route_context.new_page()
                            route_page.route("**/*", _safe_route)
                            try:
                                route_response = route_page.goto(
                                    route_url, wait_until="domcontentloaded",
                                    timeout=request.page_timeout_ms,
                                )
                                route_page.wait_for_timeout(300)
                                route_metrics = _collect_metrics(route_page)
                                findings.extend(_findings(route_metrics, "desktop"))
                                inspected_pages.append(InspectedPage(
                                    url=route_page.url,
                                    title=str(route_metrics.get("title", "")),
                                    status_code=route_response.status if route_response else None,
                                ))
                            except PlaywrightError:
                                inspected_pages.append(InspectedPage(url=route_url, title="", status_code=None))
                            finally:
                                route_context.close()
                    finally:
                        route_browser.close()
        except VisualInspectionError:
            raise
        except Exception as exc:
            raise VisualInspectionError(
                "Browser inspection could not start. Ensure the DIS browser runtime is installed."
            ) from exc

        # Keep one finding per distinct issue and viewport so the evidence stays actionable.
        unique = {(item.category, item.title, item.evidence): item for item in findings}
        findings = list(unique.values())
        visual_summary = ""
        design_observations: list[str] = []
        design_system_signals: dict[str, list[str]] = {}
        analysis_mode = "deterministic_dom_and_layout"
        vision_limitations: list[str] = []
        if request.analyze_with_vision and request.capture_screenshots:
            screenshots = [
                {"data": item.screenshot_base64, "media_type": "image/jpeg"}
                for item in viewports if item.screenshot_base64
            ]
            if screenshots:
                try:
                    visual_result = VisualDesignAnalyzer().analyze(screenshots[:3])
                    visual_summary = visual_result["summary"]
                    findings.extend(visual_result["findings"])
                    design_system_signals = visual_result["design_system"]
                    design_observations = [
                        finding.title + ": " + finding.recommendation
                        for finding in visual_result["findings"]
                    ]
                    analysis_mode = "multimodal_vision_and_deterministic"
                except (ProviderError, ValueError, TypeError):
                    vision_limitations.append(
                        "Multimodal visual analysis was unavailable; deterministic checks were used."
                    )
        elif request.analyze_with_vision:
            vision_limitations.append(
                "Enable screenshot capture and configure a vision-capable model to analyze visual aesthetics."
            )
        unique = {(item.category, item.title, item.evidence): item for item in findings}
        findings = list(unique.values())
        score, grade = _score(findings)
        return VisualInspectionResponse(
            inspected_url=target,
            page_title=page_title,
            final_url=final_url,
            status_code=status_code,
            score=score,
            grade=grade,
            findings=findings,
            metrics=aggregate,
            viewports=viewports,
            inspected_pages=inspected_pages,
            visual_summary=visual_summary,
            design_observations=design_observations,
            design_system_signals=design_system_signals,
            analysis_mode=analysis_mode,
            limitations=vision_limitations + [
                "Only same-origin anchor routes are optionally crawled, up to the configured limit; authenticated and interaction-only routes are not explored.",
                "A clean result is not a WCAG conformance certification or proof of usability.",
                "Public internet targets only; local/private network addresses and redirects to them are blocked.",
            ],
        )
