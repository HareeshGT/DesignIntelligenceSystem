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
