import pytest

from app.services.improvements import ImprovementError, ImprovementService, _repository_parts, _safe_source_path

def test_only_existing_frontend_source_paths_are_allowed():
    assert _safe_source_path("src/pages/Dashboard.tsx")
    assert _safe_source_path("styles/app.css")
    assert not _safe_source_path("../secrets.ts")
    assert not _safe_source_path(".github/workflows/release.yml")
    assert not _safe_source_path("package.json")
    assert not _safe_source_path("server.py")
    assert not _safe_source_path("src/api/client.ts")
    assert not _safe_source_path("backend/routes.ts")

def test_repository_identifier_parser_rejects_untrusted_host():
    with pytest.raises(ImprovementError):
        _repository_parts("https://evil.example/owner/repo")

def test_apply_requires_explicit_approval(monkeypatch):
    monkeypatch.setenv("DIS_GITHUB_WRITE_TOKEN", "write-token")
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "signing-key")
    with pytest.raises(ImprovementError, match="Explicit approval"):
        ImprovementService().apply("not-a-valid-token", False)


def test_signed_approval_token_can_only_be_applied_once(monkeypatch, tmp_path):
    import base64
    import hashlib
    import hmac
    import json
    import time

    monkeypatch.setenv("DIS_GITHUB_WRITE_TOKEN", "write-token")
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "signing-key")
    monkeypatch.setenv("DIS_DATABASE_PATH", str(tmp_path / "dis.sqlite"))
    payload = {
        "repository": "owner/repo",
        "ref": "main",
        "base_sha": "base-commit",
        "summary": "Improve dashboard layout",
        "changes": [{"path": "src/App.tsx", "sha": "blob-sha", "content": "export const App = () => null;"}],
        "created_at": int(time.time()),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(b"signing-key", encoded.encode(), hashlib.sha256).hexdigest()
    token = encoded + "." + signature
    service = ImprovementService()
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        if method == "GET":
            return {"object": {"sha": "base-commit"}}
        if url.endswith("/pulls"):
            return {"html_url": "https://github.com/owner/repo/pull/42", "number": 42}
        return {}

    monkeypatch.setattr(service, "_request", fake_request)
    result = service.apply(token, True)
    assert result["number"] == 42
    with pytest.raises(ImprovementError, match="already been used"):
        service.apply(token, True)
    assert len(calls) == 4


def test_secret_redaction_covers_tokens_and_private_keys():
    from app.services.improvements import _redact_secrets

    source = 'api_key = "very-long-secret-value-12345"\nTOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890'
    redacted = _redact_secrets(source)
    assert "very-long-secret-value-12345" not in redacted
    assert "ghp_abcdefghijklmnopqrstuvwxyz1234567890" not in redacted
    assert redacted.count("[REDACTED]") == 2
