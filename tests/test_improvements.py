import pytest

from app.core.improvement_models import ImprovementProposalRequest
from app.services.improvements import ImprovementError, ImprovementService, _repository_parts, _safe_source_path

def test_only_existing_frontend_source_paths_are_allowed():
    assert _safe_source_path("src/pages/Dashboard.tsx")
    assert _safe_source_path("styles/app.css")
    assert _safe_source_path("lib/screens/home_screen.dart")
    assert _safe_source_path("Sources/SettingsView.swift")
    assert _safe_source_path("app/src/main/java/ui/HomeScreen.kt")
    assert not _safe_source_path("../secrets.ts")
    assert not _safe_source_path(".github/workflows/release.yml")
    assert not _safe_source_path("package.json")
    assert not _safe_source_path("server.py")
    assert not _safe_source_path("src/api/client.ts")
    assert not _safe_source_path("backend/routes.ts")
    assert not _safe_source_path("src/api.ts")
    assert not _safe_source_path("auth.ts")
    assert not _safe_source_path("webpack.config.js")
    assert not _safe_source_path("Package.swift")
    assert not _safe_source_path("build.gradle.kts")
    assert not _safe_source_path("src/middleware.ts")
    assert not _safe_source_path("next.config.ts")

def test_repository_identifier_parser_rejects_untrusted_host():
    with pytest.raises(ImprovementError):
        _repository_parts("https://evil.example/owner/repo")

def test_apply_requires_explicit_approval(monkeypatch):
    monkeypatch.setenv("DIS_GITHUB_WRITE_TOKEN", "write-token")
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "client-api-key")
    with pytest.raises(ImprovementError, match="Explicit approval"):
        ImprovementService().apply("not-a-valid-token", False)


def test_signed_approval_token_can_only_be_applied_once(monkeypatch, tmp_path):
    import base64
    import hashlib
    import hmac
    import json
    import time

    monkeypatch.setenv("DIS_GITHUB_WRITE_TOKEN", "write-token")
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "client-api-key")
    monkeypatch.setenv("DIS_PROPOSAL_SIGNING_KEY", "proposal-signing-secret-with-32-plus-bytes")
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
    signature = hmac.new(b"proposal-signing-secret-with-32-plus-bytes", encoded.encode(), hashlib.sha256).hexdigest()
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
    json_secret = _redact_secrets('{"api_key": "json-secret-token-value-12345"}')
    assert "json-secret-token-value-12345" not in json_secret


def test_public_repository_reads_do_not_require_github_token(monkeypatch):
    monkeypatch.delenv("DIS_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("DIS_GITHUB_WRITE_TOKEN", raising=False)
    service = ImprovementService()
    captured = {}

    class Response:
        status_code = 200
        content = b"{}"

        def json(self):
            return {}

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("app.services.improvements.httpx.request", fake_request)
    service._request("GET", "https://api.github.com/repos/owner/repo")
    assert "Authorization" not in captured["headers"]
    with pytest.raises(ImprovementError, match="DIS_GITHUB_WRITE_TOKEN"):
        service._request("POST", "https://api.github.com/repos/owner/repo/git/refs", write=True)


def test_source_sharing_consent_must_be_explicitly_true():
    from pydantic import ValidationError

    base = {
        "repository": "owner/repo",
        "target_files": ["src/App.tsx"],
        "findings": [{
            "category": "visual",
            "severity": "medium",
            "title": "Improve spacing",
            "description": "The visible cards are crowded.",
            "evidence": "Cards touch at mobile width.",
            "recommendation": "Increase vertical spacing.",
        }],
    }
    with pytest.raises(ValidationError):
        ImprovementProposalRequest(**base, source_sharing_consent=False)
    request = ImprovementProposalRequest(**base, source_sharing_consent=True)
    assert request.source_sharing_consent is True


def test_proposal_rejects_missing_consent_before_github_reads(monkeypatch):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ImprovementProposalRequest(
            repository="owner/repo",
            target_files=["src/App.tsx"],
            findings=[{
                "category": "visual", "severity": "medium", "title": "Improve spacing",
                "description": "The visible cards are crowded.", "evidence": "Cards touch.",
                "recommendation": "Increase spacing.",
            }],
        )


def test_client_api_key_cannot_be_reused_as_proposal_signing_key(monkeypatch):
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "browser-client-secret")
    monkeypatch.delenv("DIS_PROPOSAL_SIGNING_KEY", raising=False)

    class EnabledProvider:
        enabled = True

    request = ImprovementProposalRequest(
        repository="owner/repo",
        target_files=["src/App.tsx"],
        findings=[{
            "category": "visual", "severity": "medium", "title": "Improve spacing",
            "description": "Cards appear crowded.", "evidence": "Visible card gap is zero.",
            "recommendation": "Increase the card gap.",
        }],
        source_sharing_consent=True,
    )
    with pytest.raises(ImprovementError, match="DIS_PROPOSAL_SIGNING_KEY"):
        ImprovementService(llm=EnabledProvider()).propose(request)


def test_proposal_signing_secret_cannot_equal_client_api_key(monkeypatch):
    shared_secret = "same-secret-used-for-client-and-signing"
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", shared_secret)
    monkeypatch.setenv("DIS_PROPOSAL_SIGNING_KEY", shared_secret)
    with pytest.raises(ImprovementError, match="must be different"):
        ImprovementService()
