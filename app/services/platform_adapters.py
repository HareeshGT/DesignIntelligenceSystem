from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PlatformProfile:
    adapter_id: str
    name: str
    runtime_family: str
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]


WEB_PROFILE = PlatformProfile(
    adapter_id="web-browser",
    name="Web application",
    runtime_family="browser",
    capabilities=("repository_inspection", "public_url_visual_audit", "desktop_tablet_mobile_screenshots", "same_origin_route_crawl", "visual_comparison", "approved_frontend_pull_requests"),
    limitations=("The app must already have a public preview URL; DIS does not build or run arbitrary repositories yet.", "Authenticated journeys and interaction-driven workflows are not supported."),
)
ELECTRON_PROFILE = PlatformProfile(
    adapter_id="electron-renderer",
    name="Electron application",
    runtime_family="web_renderer",
    capabilities=("repository_inspection", "approved_frontend_pull_requests", "visual_audit_of_supplied_renderer_url"),
    limitations=("Requires an externally provided renderer preview URL; native desktop shell automation is not available."),
)
REACT_NATIVE_PROFILE = PlatformProfile(
    adapter_id="react-native",
    name="React Native application",
    runtime_family="native_mobile",
    capabilities=("repository_inspection", "approved_frontend_source_proposals"),
    limitations=("Device/emulator screenshots and native interaction tests require a future mobile runner."),
)
FLUTTER_PROFILE = PlatformProfile(
    adapter_id="flutter-native",
    name="Flutter application",
    runtime_family="native_mobile_or_desktop",
    capabilities=("repository_inspection", "approved_frontend_source_proposals"),
    limitations=("Flutter emulator/desktop rendering and native interaction tests require a future runner."),
)
NATIVE_PROFILE = PlatformProfile(
    adapter_id="native-desktop-mobile",
    name="Native desktop/mobile application",
    runtime_family="native",
    capabilities=("repository_inspection", "approved_source_proposals_for_selected_ui_files"),
    limitations=("Native screenshots, accessibility trees and interaction tests require a platform-specific runner."),
)


def resolve_platform_profiles(frameworks: list[str], stacks: list[str]) -> list[dict]:
    labels = {value.lower() for value in frameworks}
    profiles = []
    if "electron" in labels:
        profiles.append(ELECTRON_PROFILE)
    if "react native" in labels:
        profiles.append(REACT_NATIVE_PROFILE)
    if "flutter" in labels:
        profiles.append(FLUTTER_PROFILE)
    web_labels = {"react", "next.js", "vue", "nuxt", "svelte", "angular", "astro", "vite", "tailwind css"}
    if labels.intersection(web_labels):
        profiles.append(WEB_PROFILE)
    if "swift / apple platform" in labels or "qt desktop" in labels:
        profiles.append(NATIVE_PROFILE)
    unique = {profile.adapter_id: profile for profile in profiles}
    return [asdict(profile) for profile in unique.values()]
