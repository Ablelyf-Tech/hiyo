import json, time
from device_agent.agent import Agent
from hiyo_cloud.app import create_cloud_app
from fastapi.testclient import TestClient


class MemoryKeys:
    def __init__(self):
        self.values = {}

    def put(self, name, value):
        self.values[name] = value

    def get(self, name):
        return self.values[name]


def test_daily_device_run_and_dashboard_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("HIYO_SERVICE_URL", "https://cloud.example.com")
    app = create_cloud_app(
        "sqlite+pysqlite:///:memory:",
        identity_verifier=lambda token: token,
        initialize=True,
    )
    with TestClient(app) as c:
        headers = {"Authorization": "Bearer alice"}
        ticket = c.post("/api/device-enrollment", headers=headers, json={}).json()

        def transport(url, path, body, headers):
            r = c.post(
                path,
                content=body,
                headers={"Content-Type": "application/json", **headers},
            )
            assert r.status_code == 200, r.text
            return r.json()

        agent = Agent(tmp_path / "agent", keys=MemoryKeys(), transport=transport)
        agent.enroll(ticket, "Test computer")
        workflow = {
            "name": "Local preparation",
            "steps": [
                {
                    "id": "prepare",
                    "kind": "transform",
                    "name": "Prepare",
                    "template": "Hello ${name}",
                },
                {
                    "id": "record",
                    "kind": "record",
                    "name": "Record",
                    "template": "${prepare}",
                },
            ],
        }
        wid = c.post(
            "/api/automation/workflows", headers=headers, json=workflow
        ).json()["id"]
        c.post(
            f"/api/automation/workflows/{wid}/trigger",
            headers=headers,
            json={"inputs": {"name": "Morgan"}},
        )
        assert agent.daily()["processed"] == 1
        state = c.get("/api/automation/state", headers=headers).json()
        assert state["runs"][0]["status"] == "completed"
        detail = c.get(
            "/api/automation/runs/" + state["runs"][0]["id"], headers=headers
        ).json()
        assert detail["context"]["record"] == "Hello Morgan"
        assert agent.daily()["processed"] == 0
        (agent.home / "STOP").touch()
        assert agent.daily()["status"] == "stopped"


def test_device_signing_keys_reject_plaintext_keyring_fallback(monkeypatch):
    import keyring
    import pytest
    from device_agent.agent import OSKeyStore

    Plaintext = type(
        "PlaintextKeyring", (), {"priority": 1, "__module__": "keyrings.alt.file"}
    )
    monkeypatch.setattr(keyring, "get_keyring", lambda: Plaintext())
    with pytest.raises(RuntimeError, match="plaintext"):
        OSKeyStore().put("device", "fixture-private-material")
