import base64, json, time, uuid
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient
from hiyo_cloud.app import create_cloud_app
from hiyo_cloud.auth import canonical
from hiyo_cloud.models import Job, Usage


@pytest.fixture
def cloud():
    app = create_cloud_app(
        "sqlite+pysqlite:///:memory:",
        identity_verifier=lambda token: token,
        initialize=True,
    )
    with TestClient(app) as c:
        yield c, app


def auth(uid="alice"):
    return {"Authorization": "Bearer " + uid}


def flow(c, uid="alice"):
    body = {
        "name": "Daily intake",
        "steps": [
            {
                "id": "prepare",
                "kind": "transform",
                "name": "Prepare",
                "template": "Hello ${name}",
            },
            {"id": "review", "kind": "approval", "name": "Review"},
        ],
    }
    r = c.post("/api/automation/workflows", headers=auth(uid), json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def device(c, uid="alice"):
    key = Ed25519PrivateKey.generate()
    pub = base64.b64encode(
        key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode()
    r = c.post(
        "/api/devices",
        headers=auth(uid),
        json={"name": "Test device", "public_key": pub},
    )
    assert r.status_code == 200, r.text
    return key, r.json()["id"]


def signed(c, key, did, path, body, nonce=None):
    raw = json.dumps(body, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    nonce = nonce or uuid.uuid4().hex
    sig = base64.b64encode(key.sign(canonical("POST", path, ts, nonce, raw))).decode()
    return c.post(
        path,
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hiyo-Device": did,
            "X-Hiyo-Timestamp": ts,
            "X-Hiyo-Nonce": nonce,
            "X-Hiyo-Signature": sig,
        },
    )


def test_auth_and_cross_account_isolation(cloud):
    c, a = cloud
    assert c.get("/api/account").status_code == 401
    wid = flow(c)
    assert c.get("/api/automation/state", headers=auth("bob")).json()["workflows"] == []
    assert (
        c.post(
            f"/api/automation/workflows/{wid}/trigger", headers=auth("bob"), json={}
        ).status_code
        == 404
    )
    assert c.get("/api/account", headers=auth()).json()["cost_target_usd"] == 1


def test_signed_claim_result_idempotency_and_dashboard(cloud):
    c, a = cloud
    wid = flow(c)
    key, did = device(c)
    body = {"inputs": {"name": "Morgan"}, "idempotency_key": "same-job"}
    first = c.post(
        f"/api/automation/workflows/{wid}/trigger", headers=auth(), json=body
    ).json()
    assert (
        c.post(
            f"/api/automation/workflows/{wid}/trigger", headers=auth(), json=body
        ).json()["id"]
        == first["id"]
    )
    job = signed(c, key, did, "/v1/device/claim", {}).json()["job"]
    assert job["id"] == first["id"]
    paused = {
        "lease_token": job["lease_token"],
        "status": "waiting_approval",
        "cursor": 1,
        "context": {"prepare": "Hello Morgan"},
    }
    assert (
        signed(c, key, did, f'/v1/device/jobs/{job["id"]}/result', paused).status_code
        == 200
    )
    c.post(
        f'/api/automation/runs/{job["id"]}/decision',
        headers=auth(),
        json={"approve": True},
    )
    job = signed(c, key, did, "/v1/device/claim", {}).json()["job"]
    result = {
        "lease_token": job["lease_token"],
        "status": "completed",
        "cursor": 2,
        "context": {"prepare": "Hello Morgan", "review": "Approved"},
        "evidence": [
            {
                "step_id": "prepare",
                "kind": "step_completed",
                "data": {"output": "Hello Morgan"},
                "created": time.time(),
            }
        ],
    }
    path = f'/v1/device/jobs/{job["id"]}/result'
    assert signed(c, key, did, path, result).status_code == 200
    assert signed(c, key, did, path, result).json()["duplicate"]
    state = c.get("/api/automation/state", headers=auth()).json()
    assert state["runs"][0]["status"] == "completed"
    assert c.get("/api/automation/state", headers=auth("bob")).json()["runs"] == []


def test_replay_tamper_and_revocation(cloud):
    c, a = cloud
    key, did = device(c)
    assert signed(c, key, did, "/v1/device/claim", {}, "fixed-nonce").status_code == 200
    assert signed(c, key, did, "/v1/device/claim", {}, "fixed-nonce").status_code == 401
    other = Ed25519PrivateKey.generate()
    assert signed(c, other, did, "/v1/device/claim", {}).status_code == 401
    assert c.post(f"/api/devices/{did}/revoke", headers=auth("bob")).status_code == 404
    c.post(f"/api/devices/{did}/revoke", headers=auth())
    assert signed(c, key, did, "/v1/device/claim", {}).status_code == 401


def test_quotas_and_cost_reservation(cloud, monkeypatch):
    c, a = cloud
    wid = flow(c)
    monkeypatch.setattr("hiyo_cloud.app.MAX_MONTHLY_JOBS", 1)
    assert (
        c.post(
            f"/api/automation/workflows/{wid}/trigger",
            headers=auth(),
            json={"idempotency_key": "one"},
        ).status_code
        == 200
    )
    assert (
        c.post(
            f"/api/automation/workflows/{wid}/trigger",
            headers=auth(),
            json={"idempotency_key": "two"},
        ).status_code
        == 429
    )
    usage = c.get("/api/account", headers=auth()).json()
    assert usage["jobs_used"] == 1 and usage["estimated_reserved_usd"] < 1


def test_expired_lease_and_payload_bounds(cloud):
    c, a = cloud
    wid = flow(c)
    key, did = device(c)
    assert (
        c.post(
            f"/api/automation/workflows/{wid}/trigger",
            headers=auth(),
            json={"inputs": {"large": "x" * 140000}},
        ).status_code
        == 413
    )
    c.post(f"/api/automation/workflows/{wid}/trigger", headers=auth(), json={})
    job = signed(c, key, did, "/v1/device/claim", {}).json()["job"]
    with a.state.sessions.begin() as db:
        db.get(Job, job["id"]).lease_until = 1
    result = {
        "lease_token": job["lease_token"],
        "status": "blocked",
        "cursor": 1,
        "context": {},
    }
    assert (
        signed(c, key, did, f'/v1/device/jobs/{job["id"]}/result', result).status_code
        == 409
    )
    assert (
        c.post(
            "/api/automation/workflows", headers=auth(), content="x" * 400000
        ).status_code
        == 413
    )


def test_one_use_device_enrollment_ticket(cloud, monkeypatch):
    c, a = cloud
    monkeypatch.setenv("HIYO_SERVICE_URL", "https://cloud.example.com")
    ticket = c.post("/api/device-enrollment", headers=auth(), json={}).json()
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(
        key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode()
    body = {"name": "New computer", "public_key": public, "ticket": ticket["ticket"]}
    assert c.post("/v1/enroll", json=body).status_code == 200
    assert c.post("/v1/enroll", json=body).status_code == 401


def test_sensitive_approval_only_owner_can_grant(cloud):
    c, a = cloud
    wid = flow(c)
    key, did = device(c)
    c.post(f"/api/automation/workflows/{wid}/trigger", headers=auth(), json={})
    job = signed(c, key, did, "/v1/device/claim", {}).json()["job"]
    result = {
        "lease_token": job["lease_token"],
        "status": "waiting_approval",
        "cursor": 1,
        "context": {"prepare": "Hello Morgan"},
    }
    signed(c, key, did, f'/v1/device/jobs/{job["id"]}/result', result)
    assert (
        c.post(
            f'/api/automation/runs/{job["id"]}/decision',
            headers=auth("bob"),
            json={"approve": True},
        ).status_code
        == 409
    )
    assert (
        c.post(
            f'/api/automation/runs/{job["id"]}/decision',
            headers=auth(),
            json={"approve": True},
        ).status_code
        == 200
    )
    nextjob = signed(c, key, did, "/v1/device/claim", {}).json()["job"]
    assert nextjob["approved"] == ["review"]


def test_device_cannot_complete_a_gated_job_without_cloud_approval(cloud):
    c, a = cloud
    wid = flow(c)
    key, did = device(c)
    c.post(f"/api/automation/workflows/{wid}/trigger", headers=auth(), json={})
    job = signed(c, key, did, "/v1/device/claim", {}).json()["job"]
    result = {
        "lease_token": job["lease_token"],
        "status": "completed",
        "cursor": 2,
        "context": {"prepare": "Hello", "review": "Device claims approval"},
    }
    assert (
        signed(c, key, did, f'/v1/device/jobs/{job["id"]}/result', result).status_code
        == 400
    )


def test_device_capabilities_exclude_credential_values_and_are_account_scoped(cloud):
    c, a = cloud
    key, did = device(c)
    body = {
        "connectors": [
            {
                "id": "hub",
                "name": "HubSpot",
                "base_url": "https://api.hubapi.com",
                "protocol": "rest",
                "status": "configured",
                "credential": "must-not-be-synced",
            }
        ]
    }
    assert signed(c, key, did, "/v1/device/capabilities", body).status_code == 200
    own = c.get("/api/automation/state", headers=auth()).json()
    assert any(x["name"] == "HubSpot" for x in own["connectors"])
    assert "must-not-be-synced" not in json.dumps(own)
    assert not any(
        x["name"] == "HubSpot"
        for x in c.get("/api/automation/state", headers=auth("bob")).json()[
            "connectors"
        ]
    )
