import pytest

from app.services.improvements import ImprovementError, ImprovementService, _repository_parts, _safe_source_path

def test_only_existing_frontend_source_paths_are_allowed():
    assert _safe_source_path("src/pages/Dashboard.tsx")
    assert _safe_source_path("styles/app.css")
    assert not _safe_source_path("../secrets.ts")
    assert not _safe_source_path(".github/workflows/release.yml")
    assert not _safe_source_path("package.json")
    assert not _safe_source_path("server.py")

def test_repository_identifier_parser_rejects_untrusted_host():
    with pytest.raises(ImprovementError):
        _repository_parts("https://evil.example/owner/repo")

def test_apply_requires_explicit_approval(monkeypatch):
    monkeypatch.setenv("DIS_GITHUB_WRITE_TOKEN", "write-token")
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "signing-key")
    with pytest.raises(ImprovementError, match="Explicit approval"):
        ImprovementService().apply("not-a-valid-token", False)
