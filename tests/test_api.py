from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from engineering_os.api import create_app


@pytest.fixture
def client(store, workspace):
    app = create_app(store.home, workspace.parent)
    with TestClient(app) as c:
        yield c, store, (store.home / "dashboard-token").read_text(), workspace


def test_private_api_login_and_origin(client):
    c, s, token, w = client
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/state").status_code == 401
    assert c.post("/api/login", json={"token": "wrong"}).status_code == 401
    assert c.post("/api/login", json={"token": token}).status_code == 200
    assert c.get("/api/state").status_code == 200
    assert (
        c.post(
            "/api/controller/stop", headers={"origin": "https://evil.invalid"}
        ).status_code
        == 403
    )
    assert c.get("/api/state", headers={"host": "evil.invalid"}).status_code == 400
    c.post("/api/logout")
    assert c.get("/api/state").status_code == 401


def test_workspace_validation_and_task_checks(client):
    c, s, token, w = client
    c.headers["x-dashboard-token"] = token
    body = {"name": "Test", "brief": "Build a useful feature", "workspace": str(w)}
    pid = c.post("/api/projects", json=body).json()["id"]
    assert (
        c.post("/api/projects", json={**body, "workspace": "../../"}).status_code == 400
    )
    assert (
        c.post(
            f"/api/projects/{pid}/tasks",
            json={"title": "x", "spec": "Implement a feature", "checks": []},
        ).status_code
        == 400
    )
    assert (
        c.post(
            f"/api/projects/{pid}/tasks",
            json={
                "title": "x",
                "spec": "Implement a feature",
                "checks": [["python", "-V"]],
            },
        ).status_code
        == 200
    )
    assert c.post("/api/controller/start", json={}).status_code == 400


def test_stop_and_artifact_traversal(client):
    c, s, token, w = client
    c.headers["x-dashboard-token"] = token
    assert c.post("/api/controller/stop").status_code == 200
    assert (s.home / "STOP").exists()
    assert (
        c.post("/api/controller/start", json={"approve_codex_usage": True}).status_code
        == 409
    )
    assert c.post("/api/controller/clear-stop").status_code == 200
    delivery = s.home / "artifacts" / "task"
    delivery.mkdir(parents=True)
    (delivery / "report.json").write_text('{"passed":true}')
    assert c.get("/api/artifacts/task/report.json").status_code == 200
    assert c.get("/api/artifacts/%2e%2e%2fstate.sqlite3").status_code == 404
    assert c.get("/api/artifacts/task/missing.zip").status_code == 404


def test_unicode_login_is_rejected_without_server_error(client):
    c, _, _, _ = client
    assert c.post("/api/login", json={"token": "not-a-token-🔒"}).status_code == 401
