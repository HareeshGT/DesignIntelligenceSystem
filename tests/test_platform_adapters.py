from app.services.platform_adapters import resolve_platform_profiles

def test_web_framework_resolves_browser_adapter():
    profiles = resolve_platform_profiles(["React", "Next.js"], ["JavaScript/TypeScript"])
    assert profiles[0]["adapter_id"] == "web-browser"
    assert "public_url_visual_audit" in profiles[0]["capabilities"]

def test_electron_and_native_mobile_have_explicit_runner_boundaries():
    electron = resolve_platform_profiles(["Electron"], ["JavaScript/TypeScript"])
    mobile = resolve_platform_profiles(["React Native"], ["JavaScript/TypeScript"])
    assert electron[0]["adapter_id"] == "electron-renderer"
    assert any("preview" in item.lower() for item in electron[0]["limitations"])
    assert mobile[0]["adapter_id"] == "react-native"
    assert any("emulator" in item for item in mobile[0]["limitations"])
