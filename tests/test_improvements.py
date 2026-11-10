import pytest

from app.core.improvement_models import ImprovementProposalRequest
from app.services.improvements import ImprovementError, ImprovementService, _repository_parts, _normalize_scope_path, _safe_scope_path, _safe_source_path, _ui_source_score, _decode_github_content
from app.services.llm import ProviderError

def test_github_content_decoder_accepts_wrapped_base64():
    import base64

    encoded = base64.b64encode(b"<!doctype html><html>site</html>").decode("ascii")
    wrapped = encoded[:12] + "\n" + encoded[12:]  # GitHub wraps base64 with real newlines
    assert _decode_github_content(wrapped) == "<!doctype html><html>site</html>"


def test_only_existing_frontend_source_paths_are_allowed():
    assert _safe_source_path("src/pages/Dashboard.tsx")
    assert _safe_source_path("styles/app.css")
    assert _safe_source_path("lib/screens/home_screen.dart")
    assert _safe_source_path("Sources/SettingsView.swift")
    assert _safe_source_path("app/src/main/java/ui/HomeScreen.kt")
    assert not _safe_source_path("../secrets.ts")
    assert not _safe_source_path(r"src\\api.ts")
    assert not _safe_source_path(".github/workflows/release.yml")
    assert not _safe_source_path("package.json")
    assert _safe_source_path("server.py")
    assert _safe_source_path("src/api/client.ts")
    assert _safe_source_path("backend/routes.py")
    assert _safe_source_path("src/api.ts")
    assert not _safe_source_path("auth.ts")
    assert not _safe_source_path("webpack.config.js")
    assert not _safe_source_path("Package.swift")
    assert not _safe_source_path("build.gradle.kts")
    assert not _safe_source_path("src/middleware.ts")
    assert not _safe_source_path("src/middleware/index.ts")
    assert _safe_source_path("src/api.client.ts")
    assert not _safe_source_path("next.config.ts")

def test_repository_scopes_accept_root_directories_and_python_sources():
    assert _safe_scope_path(".")
    assert _safe_scope_path("app")
    assert _safe_scope_path("app/api")
    assert _safe_scope_path("backend")
    assert not _safe_scope_path("../secrets")
    assert not _safe_scope_path(".github")
    assert not _safe_scope_path("tests")


def test_ui_source_classifier_uses_python_file_contents_not_extension():
    assert _ui_source_score("app/views.py", "from flask import render_template\\n@app.get('/dashboard')\\ndef dashboard(): return render_template('dashboard.html')") >= 8
    assert _ui_source_score("app/routes.py", "@router.get('/api/v1/dashboard')\\ndef dashboard_data(): return {'cards': []}") >= 8
    assert _ui_source_score("app/database.py", "def connect_database(): return sqlite3.connect('app.db')") == 0
    assert _ui_source_score("app/services.py", "def calculate_invoice_total(items): return sum(items)") == 0


def test_scope_normalization_accepts_common_relative_directory_forms():
    assert _normalize_scope_path("./app/web/static/") == "app/web/static"
    assert _normalize_scope_path(".\\app\\web\\static") == "app/web/static"
    assert _normalize_scope_path("./") == "."
    assert _safe_scope_path("./app/web/static/")
    assert _safe_scope_path(".")
    assert not _safe_scope_path("./../secrets")


def test_static_site_files_are_recognized_as_ui_sources():
    assert _ui_source_score("index.html", "<!doctype html><html><body>site</body></html>") >= 8
    assert _ui_source_score("assets/css/site.css", ":root { --bg: #090a12; } body { margin: 0; }") >= 5
    assert _ui_source_score("assets/js/main.js", "(() => { const nav = document.querySelector('.nav'); })();") >= 4


def test_root_scope_matches_nested_repository_files():
    from app.services.improvements import _scope_matches

    assert _scope_matches("app/views.py", ".")
    assert _scope_matches("app/views.py", "app")
    assert not _scope_matches("tests/test_views.py", "app")


def test_repository_identifier_parser_rejects_untrusted_host():
    with pytest.raises(ImprovementError):
        _repository_parts("https://evil.example/owner/repo")

def test_apply_requires_explicit_approval(monkeypatch):
    monkeypatch.setenv("DIS_GITHUB_WRITE_TOKEN", "write-token")
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "client-api-key")
    with pytest.raises(ImprovementError, match="Explicit approval"):
        ImprovementService().apply("not-a-valid-token", False)


def test_signed_approval_token_resumes_partial_apply_and_is_idempotent(monkeypatch, tmp_path):
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
        "branch_name": "dis/ui-improvement-test",
        "base_sha": "base-commit",
        "summary": "Improve dashboard layout",
        "changes": [
            {"path": "src/App.tsx", "sha": "blob-a", "content": "export const App = () => null;"},
            {"path": "src/components/Card.tsx", "sha": "blob-b", "content": "export const Card = () => null;"},
        ],
        "created_at": int(time.time()),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(b"proposal-signing-secret-with-32-plus-bytes", encoded.encode(), hashlib.sha256).hexdigest()
    token = encoded + "." + signature
    service = ImprovementService()
    branch = None
    branch_exists = False
    fail_second_file_once = True
    files = {
        "src/App.tsx": {"sha": "blob-a", "content": "old app"},
        "src/components/Card.tsx": {"sha": "blob-b", "content": "old card"},
    }
    pull_request = None
    calls = []

    def fake_request(method, url, **kwargs):
        nonlocal branch, branch_exists, fail_second_file_once, pull_request
        calls.append((method, url))
        if method == "GET" and url.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "base-commit"}}
        if method == "GET" and "/git/ref/heads/" in url:
            if not branch_exists:
                raise ImprovementError("GitHub API rejected the operation (HTTP 404).")
            return {"object": {"sha": "branch-head"}}
        if method == "POST" and url.endswith("/git/refs"):
            branch_exists = True
            branch = kwargs["json"]["ref"].removeprefix("refs/heads/")
            return {}
        if method == "GET" and url.endswith("/pulls"):
            return [pull_request] if pull_request else []
        if method == "GET" and "/contents/" in url:
            path = url.split("/contents/", 1)[1]
            item = files[path]
            return {
                "type": "file", "encoding": "base64", "sha": item["sha"],
                "content": base64.b64encode(item["content"].encode()).decode(),
            }
        if method == "PUT" and "/contents/" in url:
            path = url.split("/contents/", 1)[1]
            if path.endswith("Card.tsx") and fail_second_file_once:
                fail_second_file_once = False
                raise ImprovementError("temporary GitHub failure during second file")
            files[path] = {
                "sha": "updated-" + path,
                "content": base64.b64decode(kwargs["json"]["content"]).decode(),
            }
            return {}
        if method == "POST" and url.endswith("/pulls"):
            pull_request = {"html_url": "https://github.com/owner/repo/pull/42", "number": 42}
            return pull_request
        raise AssertionError(f"Unexpected GitHub request: {method} {url}")

    monkeypatch.setattr(service, "_request", fake_request)
    with pytest.raises(ImprovementError, match="temporary GitHub failure"):
        service.apply(token, True)

    # First file was committed; the retry skips it and finishes the second file.
    result = service.apply(token, True)
    assert result["number"] == 42
    assert files["src/App.tsx"]["content"] == payload["changes"][0]["content"]
    assert files["src/components/Card.tsx"]["content"] == payload["changes"][1]["content"]

    # A repeated client request returns the same PR and never creates a duplicate.
    repeated = service.apply(token, True)
    assert repeated == result
    assert sum(method == "POST" and url.endswith("/pulls") for method, url in calls) == 1
    assert sum(method == "PUT" for method, _ in calls) == 3


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


def test_model_provider_failures_are_mapped_to_improvement_errors(monkeypatch):
    import base64

    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "client-api-key")
    monkeypatch.setenv("DIS_PROPOSAL_SIGNING_KEY", "proposal-signing-secret-with-32-plus-bytes")
    monkeypatch.delenv("DIS_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("DIS_GITHUB_WRITE_TOKEN", raising=False)

    class BrokenProvider:
        enabled = True

        def complete_json(self, **kwargs):
            raise ProviderError("provider unavailable")

    service = ImprovementService(llm=BrokenProvider())

    def fake_request(method, url, **kwargs):
        if url.endswith("/repos/owner/repo"):
            return {"default_branch": "main"}
        if "/git/ref/heads/" in url:
            return {"object": {"sha": "base-commit"}}
        if "/git/trees/" in url:
            return {"truncated": False, "tree": [{"path": "src/App.tsx", "type": "blob"}]}
        return {
            "type": "file",
            "encoding": "base64",
            "sha": "blob-sha",
            "content": base64.b64encode(b"export const App = () => null;").decode(),
        }

    service._request = fake_request
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
    with pytest.raises(ImprovementError, match="model provider"):
        service.propose(request)


def test_proposal_accepts_empty_visual_findings_when_summary_is_available():
    request = ImprovementProposalRequest(
        repository="owner/repo",
        target_files=["src/App.tsx"],
        visual_summary="The page is visually consistent and no deterministic issues were detected.",
        source_sharing_consent=True,
    )
    assert request.findings == []


def test_proposal_requires_some_design_context_when_findings_are_empty():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="Provide at least one visual finding"):
        ImprovementProposalRequest(
            repository="owner/repo",
            target_files=["src/App.tsx"],
            source_sharing_consent=True,
        )


def test_qt_stylesheets_are_eligible_for_ai_ui_proposals():
    from app.services.improvements import _safe_source_path, _ui_source_score

    source = "QWidget { background-color: #20242b; color: #f4f4f4; }"
    assert _safe_source_path("ui/themes/dark.qss")
    assert _ui_source_score("ui/themes/dark.qss", source) > 0



def test_public_reads_do_not_fall_back_to_write_only_token(monkeypatch):
    monkeypatch.delenv("DIS_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("DIS_GITHUB_WRITE_TOKEN", "write-only-secret")
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
