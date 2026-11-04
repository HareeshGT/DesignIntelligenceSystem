from app.services.platform_adapters import resolve_platform_profiles
from app.services.github_repository import GitHubRepositoryInspector

def test_web_framework_resolves_browser_adapter():
    profiles = resolve_platform_profiles(["React", "Next.js"], ["JavaScript/TypeScript"])
    assert profiles[0]["adapter_id"] == "web-browser"
    assert "public_url_visual_audit" in profiles[0]["capabilities"]

def test_electron_and_native_mobile_have_explicit_runner_boundaries():
    electron = resolve_platform_profiles(["Electron"], ["JavaScript/TypeScript"])
    mobile = resolve_platform_profiles(["React Native"], ["JavaScript/TypeScript"])
    assert electron[0]["adapter_id"] == "electron-renderer"
    assert electron[0]["limitations"]
    assert mobile[0]["adapter_id"] == "react-native"
    assert mobile[0]["limitations"]


def test_unknown_repository_does_not_claim_web_capabilities():
    assert resolve_platform_profiles([], []) == []


def test_flutter_requires_manifest_and_dart_source():
    files = [{"path": "pubspec.yaml"}, {"path": "lib/main.dart"}]
    stacks, _, frameworks = GitHubRepositoryInspector._detect_stack(
        files, {"pubspec.yaml": "name: sample\\nflutter:\\n  uses-material-design: true"}
    )
    assert "Dart/Flutter" in stacks
    assert "Flutter" in frameworks


def test_swift_package_manifest_alone_is_not_a_native_ui_signal():
    files = [{"path": "Package.swift"}]
    _, _, frameworks = GitHubRepositoryInspector._detect_stack(files, {})
    assert "Swift / Apple platform" not in frameworks


def test_swift_xcode_project_with_swift_source_is_detected():
    files = [
        {"path": "Sample.xcodeproj/project.pbxproj"},
        {"path": "Sources/AppView.swift"},
    ]
    _, _, frameworks = GitHubRepositoryInspector._detect_stack(
        files, {"Sources/AppView.swift": "import SwiftUI\\nstruct AppView: View {}"}
    )
    assert "Swift / Apple platform" in frameworks


def test_swift_source_without_ui_framework_is_not_classified_as_app():
    files = [{"path": "Package.swift"}, {"path": "Sources/Utility.swift"}]
    _, _, frameworks = GitHubRepositoryInspector._detect_stack(
        files, {"Sources/Utility.swift": "import Foundation\\nstruct Helper {}"}
    )
    assert "Swift / Apple platform" not in frameworks
