import base64

import pytest

from app.services.github_repository import (
    GitHubRepositoryInspector,
    RepositoryInspectionError,
    _parse_repository,
    _safe_path,
)


def test_parse_github_url_and_identifier():
    assert _parse_repository("HareeshGT/KubeDock") == ("HareeshGT", "KubeDock")
    assert _parse_repository("https://github.com/HareeshGT/KubeDock.git") == ("HareeshGT", "KubeDock")


@pytest.mark.parametrize("value", [
    "https://evil.example/user/repo",
    "owner",
    "owner/repo/extra",
    "../repo",
    "owner/..",
])
def test_rejects_invalid_repository_identifiers(value):
    with pytest.raises(RepositoryInspectionError):
        _parse_repository(value)


def test_sensitive_and_generated_paths_are_excluded():
    assert not _safe_path(".env")
    assert not _safe_path("config/.env.production")
    assert not _safe_path("secrets.yaml")
    assert not _safe_path("id_rsa")
    assert not _safe_path("node_modules/react/index.js")
    assert not _safe_path("src/../secret.txt")
    assert _safe_path("src/components/Dashboard.tsx")


def test_detect_stack_and_frameworks_from_manifests():
    files = [
        {"path": "package.json"}, {"path": "pnpm-lock.yaml"},
        {"path": "src/main.tsx"}, {"path": "src/components/Dashboard.tsx"},
    ]
    contents = {
        "package.json": '{"dependencies":{"react":"^18","vite":"^5","tailwindcss":"^3"}}'
    }
    stacks, managers, frameworks = GitHubRepositoryInspector._detect_stack(files, contents)
    assert "JavaScript/TypeScript" in stacks
    assert "pnpm" in managers
    assert "React" in frameworks
    assert "Vite" in frameworks
    assert "Tailwind CSS" in frameworks


def test_commands_are_reported_as_not_executed():
    commands = GitHubRepositoryInspector._commands({
        "package.json": '{"scripts":{"test":"vitest run","lint":"eslint .","build":"vite build"}}'
    })
    assert "npm run test (declared; not executed)" in commands
    assert "npm run lint (declared; not executed)" in commands
    assert "npm run build (declared; not executed)" in commands
