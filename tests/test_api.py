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
