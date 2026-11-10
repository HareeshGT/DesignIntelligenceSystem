from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_agents_endpoint_returns_seven_roles():
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    assert len(response.json()) == 7


def test_design_run_endpoint():
    response = client.post("/api/v1/design/runs", json={"brief": "Design a SaaS onboarding experience"})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 7


def test_repository_inspection_requires_configured_api_key(monkeypatch):
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "test-secret")
    monkeypatch.delenv("DIS_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("DIS_LLM_API_KEY", raising=False)
    response = client.post(
        "/api/v1/repositories/inspect",
        json={"repository": "invalid/too/many/segments"},
    )
    assert response.status_code == 401


def test_repository_inspection_rejects_invalid_repository_identifier(monkeypatch):
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "test-secret")
    monkeypatch.delenv("DIS_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("DIS_LLM_API_KEY", raising=False)
    response = client.post(
        "/api/v1/repositories/inspect",
        headers={"X-DIS-API-Key": "test-secret"},
        json={"repository": "invalid/too/many/segments"},
    )
    assert response.status_code == 400


def test_dashboard_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Design Intelligence System" in response.text
    assert "/static/app.css" in response.text


def test_dashboard_assets_are_served():
    response = client.get("/static/app.js")
    assert response.status_code == 200
    assert "api/v1/repositories/inspect" in response.text


def test_visual_inspection_requires_shared_key_when_configured(monkeypatch):
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "visual-secret")
    monkeypatch.delenv("DIS_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("DIS_LLM_API_KEY", raising=False)
    response = client.post(
        "/api/v1/visual/inspect",
        json={"url": "https://example.com"},
    )
    assert response.status_code == 401


def test_visual_inspection_rejects_missing_shared_key_configuration(monkeypatch):
    monkeypatch.delenv("DIS_REPOSITORY_INSPECTION_API_KEY", raising=False)
    monkeypatch.setenv("DIS_LLM_API_KEY", "configured-provider-key")
    monkeypatch.delenv("DIS_GITHUB_TOKEN", raising=False)
    response = client.post(
        "/api/v1/visual/inspect",
        json={"url": "https://example.com"},
    )
    assert response.status_code == 503


def test_visual_inspection_rejects_localhost_before_browser_launch(monkeypatch):
    monkeypatch.delenv("DIS_REPOSITORY_INSPECTION_API_KEY", raising=False)
    monkeypatch.delenv("DIS_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DIS_GITHUB_TOKEN", raising=False)
    response = client.post(
        "/api/v1/visual/inspect",
        json={"url": "http://localhost:8000"},
    )
    assert response.status_code == 400


def test_improvement_endpoints_require_shared_api_key(monkeypatch):
    monkeypatch.delenv("DIS_REPOSITORY_INSPECTION_API_KEY", raising=False)
    response = client.post(
        "/api/v1/improvements/propose",
        json={"repository":"owner/repo","target_files":["src/App.tsx"],"findings":[{"category":"visual","severity":"medium","title":"test","description":"test issue","evidence":"visible in screenshot","recommendation":"adjust layout"}],"source_sharing_consent":True},
    )
    assert response.status_code == 503


def test_improvement_endpoints_reject_invalid_api_key(monkeypatch):
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "expected-secret")
    response = client.post(
        "/api/v1/improvements/propose",
        headers={"X-DIS-API-Key":"wrong"},
        json={"repository":"owner/repo","target_files":["src/App.tsx"],"findings":[{"category":"visual","severity":"medium","title":"test","description":"test issue","evidence":"visible in screenshot","recommendation":"adjust layout"}],"source_sharing_consent":True},
    )
    assert response.status_code == 401


def test_visual_compare_requires_shared_key_when_configured(monkeypatch):
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "compare-secret")
    monkeypatch.delenv("DIS_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("DIS_LLM_API_KEY", raising=False)
    response = client.post(
        "/api/v1/visual/compare",
        json={"baseline_url":"https://before.example","candidate_url":"https://after.example"},
    )
    assert response.status_code == 401


def test_visual_api_key_comparison_handles_non_ascii_header_values():
    from app.api.visual import _api_key_matches

    assert _api_key_matches("é", "expected-secret") is False
    assert _api_key_matches("expected-secret", "expected-secret") is True


def test_provider_status_uses_resolved_vision_provider_configuration(monkeypatch):
    monkeypatch.setenv("DIS_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DIS_LLM_API_KEY", "text-secret")
    monkeypatch.setenv("DIS_LLM_MODEL", "text-model")
    monkeypatch.setenv("DIS_LLM_BASE_URL", "https://text-provider.example/v1")
    for name in ("DIS_VISION_LLM_PROVIDER", "DIS_VISION_LLM_API_KEY", "DIS_VISION_LLM_MODEL", "DIS_VISION_LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    response = client.get("/api/v1/provider")
    assert response.status_code == 200
    assert response.json()["vision_configured"] is True
    assert response.json()["vision_provider"] == "openai-compatible"


def test_provider_status_does_not_report_partial_vision_config_as_enabled(monkeypatch):
    monkeypatch.setenv("DIS_LLM_API_KEY", "text-secret")
    monkeypatch.setenv("DIS_LLM_MODEL", "text-model")
    monkeypatch.setenv("DIS_LLM_BASE_URL", "https://text-provider.example/v1")
    monkeypatch.delenv("DIS_VISION_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("DIS_VISION_LLM_API_KEY", "")
    monkeypatch.setenv("DIS_VISION_LLM_MODEL", "vision-model")
    monkeypatch.delenv("DIS_VISION_LLM_BASE_URL", raising=False)

    response = client.get("/api/v1/provider")
    assert response.status_code == 200
    assert response.json()["vision_configured"] is False
    assert response.json()["vision_provider"] is None


def test_provider_status_uses_request_scoped_user_model_without_exposing_key():
    response = client.get(
        "/api/v1/provider",
        headers={
            "X-DIS-LLM-Provider": "openai-compatible",
            "X-DIS-LLM-Model": "user-model",
            "X-DIS-LLM-API-Key": "user-secret-never-return-this",
            "X-DIS-LLM-Base-URL": "https://api.example.com/v1",
        },
    )
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert response.json()["provider"] == "openai-compatible"
    assert response.json()["model"] == "user-model"
    assert "user-secret-never-return-this" not in response.text


def test_request_scoped_llm_key_does_not_require_server_shared_key_for_design_run(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.delenv("DIS_REPOSITORY_INSPECTION_API_KEY", raising=False)
    for name in ("DIS_GITHUB_TOKEN", "DIS_GITHUB_WRITE_TOKEN", "DIS_LLM_API_KEY", "DIS_VISION_LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("app.main.request_llm", lambda *args, **kwargs: SimpleNamespace(enabled=True))
    monkeypatch.setattr(
        "app.main.Orchestrator.run",
        lambda self, request: SimpleNamespace(model_dump=lambda **kwargs: {"results": []}),
    )
    response = client.post(
        "/api/v1/design/runs",
        headers={"X-DIS-LLM-API-Key": "caller-owned-key", "X-DIS-LLM-Provider": "mistral"},
        json={"brief": "Improve the product dashboard UI"},
    )
    assert response.status_code == 200


def test_request_scoped_credentials_do_not_require_server_key_for_repository_inspection(monkeypatch):
    from types import SimpleNamespace
    from app.services.github_repository import RepositoryInspectionError

    monkeypatch.delenv("DIS_REPOSITORY_INSPECTION_API_KEY", raising=False)
    for name in ("DIS_GITHUB_TOKEN", "DIS_GITHUB_WRITE_TOKEN", "DIS_LLM_API_KEY", "DIS_VISION_LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("app.api.repositories.request_llm", lambda *args, **kwargs: SimpleNamespace(enabled=True))
    def reject_inspection(*args, **kwargs):
        raise RepositoryInspectionError("test reached repository inspection")
    monkeypatch.setattr("app.api.repositories.GitHubRepositoryInspector.inspect", reject_inspection)
    response = client.post(
        "/api/v1/repositories/inspect",
        headers={"X-DIS-LLM-API-Key": "caller-owned-key", "X-DIS-LLM-Provider": "mistral"},
        json={"repository": "owner/repository", "include_file_samples": False},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "test reached repository inspection"


def test_request_scoped_llm_key_does_not_require_server_shared_key_for_visual_inspection(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.delenv("DIS_REPOSITORY_INSPECTION_API_KEY", raising=False)
    for name in ("DIS_GITHUB_TOKEN", "DIS_GITHUB_WRITE_TOKEN", "DIS_LLM_API_KEY", "DIS_VISION_LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "app.api.visual.VisualInspector.inspect",
        lambda self, request: SimpleNamespace(model_dump=lambda **kwargs: {"status": "ok"}),
    )
    response = client.post(
        "/api/v1/visual/inspect",
        headers={"X-DIS-LLM-API-Key": "caller-owned-key", "X-DIS-LLM-Provider": "mistral"},
        json={"url": "https://example.com"},
    )
    assert response.status_code == 200


def test_improvement_proposal_accepts_studio_sized_payload_before_auth(monkeypatch):
    """Regression: the Studio client sends up to 10000 chars of specialist context.

    A 422 here (validation) would mask everything behind it; getting the 401 means
    the payload passed request validation and reached the API-key check.
    """
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "expected-secret")
    response = client.post(
        "/api/v1/improvements/propose",
        headers={"X-DIS-API-Key": "wrong"},
        json={
            "repository": "owner/repo",
            "target_files": ["src/App.tsx"],
            "design_brief": "Redesign the dashboard. " * 200,
            "findings": [{
                "category": "design_brief", "severity": "Critical", "title": "t" * 400,
                "description": "d" * 2000, "evidence": "", "recommendation": "r" * 2000,
            }],
            "visual_summary": "Specialist: " + "context " * 1500,
            "source_sharing_consent": True,
        },
    )
    assert response.status_code == 401


def test_improvement_proposal_validation_errors_are_still_422(monkeypatch):
    monkeypatch.setenv("DIS_REPOSITORY_INSPECTION_API_KEY", "expected-secret")
    response = client.post(
        "/api/v1/improvements/propose",
        headers={"X-DIS-API-Key": "expected-secret"},
        json={"repository": "owner/repo", "target_files": [], "source_sharing_consent": True},
    )
    assert response.status_code == 422



def test_dashboard_credential_helper_requires_explicit_scopes():
    response = client.get("/static/app.js")
    source = response.text
    assert "function apiHeaders({apiKey = false, llm = false, githubRead = false, githubWrite = false}" in source
    assert "headers:apiHeaders({apiKey:true,githubWrite:true})" in source
    assert "headers:apiHeaders({apiKey:true,llm:true,githubRead:true})" in source
    assert "if (githubWrite && values.githubWrite)" in source



def test_proposal_endpoint_does_not_accept_a_github_write_token():
    from inspect import signature
    from app.api.improvements import propose_improvement, apply_improvement

    assert "github_write_token" not in signature(propose_improvement).parameters
    assert "github_write_token" in signature(apply_improvement).parameters



def test_settings_expose_supported_compatible_providers_and_scoped_visual_key():
    html = client.get("/").text
    script = client.get("/static/app.js").text
    assert '<option value="groq">Groq</option>' in html
    assert '<option value="openrouter">OpenRouter</option>' in html
    assert 'groq: {baseUrl:"https://api.groq.com/openai/v1"' in script
    assert 'openrouter: {baseUrl:"https://openrouter.ai/api/v1"' in script
    assert 'llm:$("vision-analysis").checked' in script
