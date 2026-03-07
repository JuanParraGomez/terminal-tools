from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_route_endpoint() -> None:
    client = TestClient(app)
    resp = client.post(
        "/route",
        json={
            "user_goal": "hazme un plan de implementación",
            "needs_plan": True,
            "complexity": 3,
            "target_environment": "local",
            "requires_iteration": False,
            "requires_code_changes": False,
            "needs_second_opinion": False,
            "allowed_mutation_level": "readonly",
        },
    )
    assert resp.status_code == 200
    assert "selected_tool" in resp.json()


def test_path_policy_endpoints() -> None:
    client = TestClient(app)
    resp = client.get("/path-policy")
    assert resp.status_code == 200
    check = client.post("/path-policy/check", json={"path": "/home/juan/Documents/.env", "action": "read"})
    assert check.status_code == 200
    assert check.json()["allowed"] is False


def test_trash_endpoints() -> None:
    client = TestClient(app)
    created = client.post("/trash/create", json={"task_id": "api-test", "label": "tmp"})
    assert created.status_code == 200
    listed = client.get("/trash")
    assert listed.status_code == 200
    assert "items" in listed.json()
