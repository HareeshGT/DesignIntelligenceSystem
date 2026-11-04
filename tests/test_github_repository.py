import pytest

from app.services.github_repository import (
    GitHubRepositoryInspector,
    RepositoryInspectionError,
    _parse_repository,
    _redact_text,
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


def test_likely_embedded_credentials_are_redacted():
    text = 'api_key="sk-123456789012345678901234" Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456'
    redacted = _redact_text(text)
    assert "sk-123456789012345678901234" not in redacted
    assert "abcdefghijklmnopqrstuvwxyz123456" not in redacted
    assert "[REDACTED]" in redacted


def test_inspector_builds_read_only_inventory_from_github_api(monkeypatch):
    import json
    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    package = json.dumps({
        "dependencies": {"react": "^18", "vite": "^5"},
        "scripts": {"test": "vitest run"},
    }).encode()
    readme = b"# Demo app"
    files = [
        {"path": "package.json", "type": "blob"},
        {"path": "README.md", "type": "blob"},
        {"path": "src/main.tsx", "type": "blob"},
        {"path": "src/components/Dashboard.tsx", "type": "blob"},
        {"path": ".env", "type": "blob"},
    ]

    def fake_get(url, headers=None, params=None, timeout=None):
        if url.endswith("/repos/acme/demo"):
            return FakeResponse({"default_branch": "main", "description": "Demo", "language": "TypeScript"})
        if "/git/trees/" in url:
            return FakeResponse({"tree": files, "truncated": False})
        path = url.split("/contents/", 1)[1]
        content = {"package.json": package, "README.md": readme}.get(path, b"")
        return FakeResponse({
            "encoding": "base64",
            "content": __import__("base64").b64encode(content).decode(),
        })

    monkeypatch.setattr("app.services.github_repository.httpx.get", fake_get)
    result = GitHubRepositoryInspector().inspect("acme/demo")
    assert result.repository == "acme/demo"
    assert result.ref == "main"
    assert "React" in result.frameworks
    assert "Vite" in result.frameworks
    assert "src/main.tsx" in result.app_entry_points
    assert "npm run test (declared; not executed)" in result.test_and_lint_commands
    assert all(".env" not in item.path for item in result.file_evidence)
    assert any("was executed" in item for item in result.limitations)
