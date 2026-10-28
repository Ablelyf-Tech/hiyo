from __future__ import annotations
import base64
import hashlib
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, func, or_, and_
from sqlalchemy.exc import IntegrityError
from .models import (
    Base,
    Account,
    Device,
    Nonce,
    Usage,
    Job,
    CloudWorkflow,
    EnrollmentTicket,
    ApprovalAudit,
    database,
)
from .auth import firebase_identity, verify_device
from engineering_os.automation import Workflow, CATALOG

MAX_MONTHLY_JOBS = 1000
MAX_MONTHLY_BYTES = 64 * 1024 * 1024
COST_TARGET = 1_000_000  # micro USD; application estimate, not a provider invoice cap.
BASE_RESERVE = 250_000
PER_JOB_RESERVE = 500


class Enrollment(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    public_key: str = Field(min_length=40, max_length=100)


class TicketEnrollment(Enrollment):
    ticket: str = Field(min_length=32, max_length=100)


class Trigger(BaseModel):
    inputs: dict = Field(default_factory=dict)
    idempotency_key: str = Field(
        default_factory=lambda: uuid.uuid4().hex, max_length=100
    )


class Result(BaseModel):
    lease_token: str = Field(max_length=80)
    status: str = Field(pattern=r"^(completed|waiting_approval|blocked|skipped)$")
    cursor: int = Field(ge=0, le=20)
    context: dict
    evidence: list = Field(default_factory=list, max_length=60)
    error: str | None = Field(default=None, max_length=1000)


class Decision(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=1000)


class Enabled(BaseModel):
    enabled: bool


class Capabilities(BaseModel):
    connectors: list[dict] = Field(default_factory=list, max_length=50)


def create_cloud_app(
    url=None, identity_verifier=None, initialize=False, dashboard=None
):
    db_url = url or os.environ.get("HIYO_DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "HIYO_DATABASE_URL is required; production must use PostgreSQL"
        )
    if not url and not db_url.startswith("postgresql"):
        raise RuntimeError("Cloud production requires PostgreSQL")
    engine, sessions = database(db_url)
    if initialize:
        Base.metadata.create_all(
            engine
        )  # tests/development only; production uses migration job.
    verifier = identity_verifier or (
        lambda token: firebase_identity(
            token, os.environ.get("HIYO_FIREBASE_PROJECT", "")
        )
    )
    app = FastAPI(
        title="Hiyo Cloud Coordination", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.sessions = sessions
    app.state.engine = engine

    @app.middleware("http")
    async def boundaries(request, call_next):
        # Bound actual streamed bodies, including chunked requests without Content-Length.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 300 * 1024:
                return Response("Request exceeds 300 KiB", status_code=413)
        request._body = bytes(body)
        request.scope["hiyo_body_digest"] = hashlib.sha256(body).hexdigest()
        response = await call_next(request)
        uid = getattr(request.state, "account_id", None)
        size = int(response.headers.get("content-length", "0"))
        if (
            uid
            and request.url.path not in ("/api/account",)
            and 200 <= response.status_code < 300
        ):
            with sessions.begin() as db:
                ledger = usage(db, uid)
                if ledger.bytes_used + size > MAX_MONTHLY_BYTES:
                    return Response(
                        "Monthly sync and dashboard byte allowance reached",
                        status_code=429,
                    )
                ledger.bytes_used += size
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self' https://*.googleapis.com https://*.firebaseapp.com https://securetoken.googleapis.com; frame-src https://*.firebaseapp.com; script-src 'self' https://apis.google.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.googleusercontent.com; frame-ancestors 'none'"
        )
        return response

    def user(request: Request):
        bearer = request.headers.get("authorization", "")
        if not bearer.startswith("Bearer "):
            raise HTTPException(401, "Firebase identity required")
        uid = verifier(bearer[7:])
        if not isinstance(uid, str) or not 1 <= len(uid) <= 128:
            raise HTTPException(401, "Invalid identity")
        with sessions.begin() as db:
            account = db.get(Account, uid)
            if not account:
                # Concurrent first logins are protected by the account primary key.
                try:
                    with db.begin_nested():
                        db.add(Account(id=uid))
                        db.flush()
                except IntegrityError:
                    pass
                account = db.get(Account, uid)
            if account and account.disabled:
                raise HTTPException(403, "Account disabled")
        request.state.account_id = uid
        with sessions.begin() as db:
            ledger = usage(db, uid)
            if ledger.requests >= 10000 and request.url.path != "/api/account":
                raise HTTPException(429, "Monthly API request allowance reached")
            ledger.requests += 1
        return uid

    async def device(request: Request):
        uid, did = await verify_device(request, sessions)
        with sessions() as db:
            account = db.get(Account, uid)
            if not account or account.disabled:
                raise HTTPException(403, "Account disabled")
        request.state.account_id = uid
        with sessions.begin() as db:
            ledger = usage(db, uid)
            if ledger.requests >= 10000:
                raise HTTPException(429, "Monthly API request allowance reached")
            ledger.requests += 1
        return uid, did

    def usage(db, uid):
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        row = db.scalar(
            select(Usage)
            .where(Usage.account_id == uid, Usage.month == month)
            .with_for_update()
        )
        if row is None:
            try:
                with db.begin_nested():
                    row = Usage(
                        account_id=uid,
                        month=month,
                        jobs=0,
                        bytes_used=0,
                        reserved_microusd=BASE_RESERVE,
                    )
                    db.add(row)
                    db.flush()
            except IntegrityError:
                row = db.scalar(
                    select(Usage)
                    .where(Usage.account_id == uid, Usage.month == month)
                    .with_for_update()
                )
        return row

    def enqueue(db, uid, flow, inputs, key):
        if any(
            not isinstance(k, str)
            or not k.isidentifier()
            or k.startswith("_")
            or len(k) > 50
            for k in inputs
        ):
            raise HTTPException(
                400, "Input keys must be simple identifiers up to 50 characters"
            )
        if not flow.enabled:
            raise HTTPException(409, "Workflow paused")
        existing = db.scalar(
            select(Job).where(Job.account_id == uid, Job.idempotency_key == key)
        )
        if existing:
            return existing
        payload = json.dumps(
            {"workflow": json.loads(flow.definition), "inputs": inputs},
            separators=(",", ":"),
        )
        size = len(payload.encode())
        if size > 128 * 1024:
            raise HTTPException(413, "Device payload exceeds 128 KiB")
        ledger = usage(db, uid)
        # Recheck after the account/month lock to make concurrent idempotent requests safe.
        existing = db.scalar(
            select(Job).where(Job.account_id == uid, Job.idempotency_key == key)
        )
        if existing:
            return existing
        if (
            ledger.jobs >= MAX_MONTHLY_JOBS
            or ledger.bytes_used + size > MAX_MONTHLY_BYTES
            or ledger.reserved_microusd + PER_JOB_RESERVE > COST_TARGET
        ):
            raise HTTPException(
                429,
                "Monthly included usage or application cost-reservation limit reached",
            )
        ledger.jobs += 1
        ledger.bytes_used += size
        ledger.reserved_microusd += PER_JOB_RESERVE
        job = Job(
            id=str(uuid.uuid4()),
            account_id=uid,
            workflow_id=flow.id,
            idempotency_key=key,
            payload=payload,
            status="queued",
            attempts=0,
            approved="[]",
            lease_until=0,
        )
        db.add(job)
        db.flush()
        return job

    def owner_flow(db, uid, wid):
        row = db.scalar(
            select(CloudWorkflow).where(
                CloudWorkflow.id == wid, CloudWorkflow.account_id == uid
            )
        )
        if not row:
            raise HTTPException(404, "Workflow not found")
        return row

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "hiyo-cloud"}

    @app.get("/api/state")
    def base_state(uid=Depends(user)):
        return {
            "projects": [],
            "tasks": [],
            "events": [],
            "runs": [],
            "artifacts": [],
            "running": False,
            "cloud": True,
        }

    @app.get("/api/account")
    def account(uid=Depends(user)):
        with sessions.begin() as db:
            ledger = usage(db, uid)
            devices = db.scalars(select(Device).where(Device.account_id == uid)).all()
            return {
                "account_id": uid,
                "cost_target_usd": 1,
                "estimated_reserved_usd": ledger.reserved_microusd / 1_000_000,
                "month": ledger.month,
                "jobs_used": ledger.jobs,
                "jobs_limit": MAX_MONTHLY_JOBS,
                "bytes_used": ledger.bytes_used,
                "bytes_limit": MAX_MONTHLY_BYTES,
                "api_requests": ledger.requests,
                "api_requests_limit": 10000,
                "devices": [
                    {
                        "id": d.id,
                        "name": d.name,
                        "active": d.active,
                        "last_seen": d.last_seen,
                    }
                    for d in devices
                ],
            }

    @app.post("/api/devices")
    def enroll(body: Enrollment, uid=Depends(user)):
        try:
            key = base64.b64decode(body.public_key, validate=True)
            if len(key) != 32:
                raise ValueError()
        except ValueError as exc:
            raise HTTPException(400, "Ed25519 public key required") from exc
        with sessions.begin() as db:
            db.scalar(select(Account).where(Account.id == uid).with_for_update())
            count = db.scalar(
                select(func.count())
                .select_from(Device)
                .where(Device.account_id == uid, Device.active.is_(True))
            )
            if count >= 3:
                raise HTTPException(
                    429, "Three active devices are included per account"
                )
            did = str(uuid.uuid4())
            db.add(
                Device(
                    id=did,
                    account_id=uid,
                    name=body.name,
                    public_key=body.public_key,
                    active=True,
                )
            )
        return {
            "id": did,
            "account_id": uid,
            "default_sync": "daily",
            "daily_jitter_seconds": 3600,
        }

    @app.post("/api/device-enrollment")
    def ticket(uid=Depends(user)):
        if not os.environ.get("HIYO_SERVICE_URL", "").startswith("https://"):
            raise HTTPException(
                503, "Configure the deployed HTTPS service URL before enrollment"
            )
        token = secrets.token_urlsafe(32)
        with sessions.begin() as db:
            db.scalar(select(Account).where(Account.id == uid).with_for_update())
            pending = db.scalar(
                select(func.count())
                .select_from(EnrollmentTicket)
                .where(
                    EnrollmentTicket.account_id == uid,
                    EnrollmentTicket.consumed.is_(False),
                    EnrollmentTicket.expires > time.time(),
                )
            )
            if pending >= 3:
                raise HTTPException(
                    429, "Three pending enrollment tickets already exist"
                )
            db.add(
                EnrollmentTicket(
                    digest=hashlib.sha256(token.encode()).hexdigest(),
                    account_id=uid,
                    expires=time.time() + 900,
                    consumed=False,
                )
            )
        return {
            "cloud_url": os.environ.get("HIYO_SERVICE_URL", ""),
            "ticket": token,
            "expires": time.time() + 900,
        }

    @app.post("/v1/enroll")
    def enroll_ticket(body: TicketEnrollment):
        digest = hashlib.sha256(body.ticket.encode()).hexdigest()
        with sessions.begin() as db:
            row = db.scalar(
                select(EnrollmentTicket)
                .where(EnrollmentTicket.digest == digest)
                .with_for_update()
            )
            if not row or row.consumed or row.expires < time.time():
                raise HTTPException(401, "Enrollment ticket expired or already used")
            account = db.get(Account, row.account_id)
            if not account or account.disabled:
                raise HTTPException(403)
            uid = row.account_id
            # The enclosing transaction locks the one-use ticket; roll back on enrollment failure.
            try:
                key = base64.b64decode(body.public_key, validate=True)
                if len(key) != 32:
                    raise ValueError()
            except ValueError as exc:
                raise HTTPException(400, "Ed25519 public key required") from exc
            db.scalar(select(Account).where(Account.id == uid).with_for_update())
            count = db.scalar(
                select(func.count())
                .select_from(Device)
                .where(Device.account_id == uid, Device.active.is_(True))
            )
            if count >= 3:
                raise HTTPException(429, "Three active devices are included")
            did = str(uuid.uuid4())
            db.add(
                Device(
                    id=did,
                    account_id=uid,
                    name=body.name,
                    public_key=body.public_key,
                    active=True,
                )
            )
            row.consumed = True
        return {
            "id": did,
            "account_id": uid,
            "default_sync": "daily",
            "daily_jitter_seconds": 3600,
        }

    @app.post("/api/devices/{did}/revoke")
    def revoke(did: str, uid=Depends(user)):
        with sessions.begin() as db:
            d = db.scalar(
                select(Device).where(Device.id == did, Device.account_id == uid)
            )
            if not d:
                raise HTTPException(404)
            d.active = False
        return {"revoked": True}

    @app.post("/api/automation/workflows")
    def workflow(body: Workflow, uid=Depends(user)):
        if len(body.model_dump_json().encode()) > 16384:
            raise HTTPException(413, "Cloud workflow definition exceeds 16 KiB")
        with sessions.begin() as db:
            count = db.scalar(
                select(func.count())
                .select_from(CloudWorkflow)
                .where(CloudWorkflow.account_id == uid)
            )
            if count >= 100:
                raise HTTPException(429, "100 workflows per account are included")
            wid = str(uuid.uuid4())
            db.add(
                CloudWorkflow(
                    id=wid,
                    account_id=uid,
                    definition=body.model_dump_json(),
                    enabled=body.enabled,
                    next_run=time.time() + 86400,
                )
            )
        return {"id": wid}

    @app.post("/api/automation/templates/{tid}")
    def template(tid: str, uid=Depends(user)):
        t = next((t for t in CATALOG["templates"] if t["id"] == tid), None)
        if not t:
            raise HTTPException(404)
        return workflow(
            Workflow(**{k: v for k, v in t.items() if k not in ("id", "example")}), uid
        )

    @app.post("/api/automation/workflows/{wid}/enabled")
    def enabled(wid: str, body: Enabled, uid=Depends(user)):
        with sessions.begin() as db:
            owner_flow(db, uid, wid).enabled = body.enabled
        return {"enabled": body.enabled}

    @app.post("/api/automation/workflows/{wid}/trigger")
    def trigger(wid: str, body: Trigger, uid=Depends(user)):
        with sessions.begin() as db:
            job = enqueue(
                db, uid, owner_flow(db, uid, wid), body.inputs, body.idempotency_key
            )
        return {"id": job.id, "status": "queued", "execution": "enrolled device"}

    @app.post("/api/automation/runs/{rid}/decision")
    def decide(rid: str, body: Decision, uid=Depends(user)):
        with sessions.begin() as db:
            j = db.scalar(
                select(Job)
                .where(Job.id == rid, Job.account_id == uid)
                .with_for_update()
            )
            if not j or j.status != "waiting_approval" or not j.result:
                raise HTTPException(409, "Run is not waiting for approval")
            result = json.loads(j.result)
            steps = json.loads(j.payload)["workflow"]["steps"]
            if result["cursor"] >= len(steps):
                raise HTTPException(409, "Invalid approval cursor")
            db.add(
                ApprovalAudit(
                    id=str(uuid.uuid4()),
                    job_id=j.id,
                    account_id=uid,
                    step_id=steps[result["cursor"]]["id"],
                    approved=body.approve,
                    note=body.note,
                )
            )
            if body.approve:
                approved = json.loads(j.approved)
                approved.append(steps[result["cursor"]]["id"])
                j.approved = json.dumps(approved)
                j.status = "queued"
                j.lease_until = 0
            else:
                j.status = "cancelled"
            j.updated = time.time()
        return {
            "status": j.status,
            "sync": "The enrolled computer will continue at its next sync",
        }

    @app.post("/api/automation/runs/{rid}/resume")
    def resume(rid: str, uid=Depends(user)):
        with sessions.begin() as db:
            j = db.scalar(
                select(Job)
                .where(Job.id == rid, Job.account_id == uid, Job.status == "blocked")
                .with_for_update()
            )
            if not j:
                raise HTTPException(409, "Blocked run not found")
            payload = json.loads(j.payload)
            payload["operator_resume"] = uuid.uuid4().hex
            j.payload = json.dumps(payload)
            j.status = "queued"
            j.attempts = 0
            j.lease_until = 0
        return {"status": "queued"}

    @app.get("/api/automation/state")
    def state(uid=Depends(user)):
        with sessions() as db:
            flows = db.scalars(
                select(CloudWorkflow)
                .where(CloudWorkflow.account_id == uid)
                .order_by(CloudWorkflow.created.desc())
            ).all()
            jobs = db.scalars(
                select(Job)
                .where(Job.account_id == uid)
                .order_by(Job.created.desc())
                .limit(100)
            ).all()
            devices = db.scalars(
                select(Device).where(Device.account_id == uid, Device.active.is_(True))
            ).all()
            connectors = [
                {
                    **entry,
                    "category": "Universal connector on " + d.name,
                    "description": "Credentials stay on the enrolled device. REST, GraphQL, SOAP or webhook actions require approval.",
                }
                for d in devices
                for entry in json.loads(d.capabilities or "[]")
            ]
        runs = []
        evidence = []
        for job in jobs:
            payload = json.loads(job.payload)
            result = json.loads(job.result) if job.result else {}
            runs.append(
                {
                    "id": job.id,
                    "workflow_id": job.workflow_id,
                    "workflow": payload["workflow"],
                    "inputs": {},
                    "status": job.status,
                    "cursor": result.get("cursor", 0),
                    "context": {},
                    "created": job.created,
                    "error": result.get("error"),
                    "approved": json.loads(job.approved),
                }
            )

        return {
            "workflows": [
                {
                    "id": w.id,
                    "name": json.loads(w.definition)["name"],
                    "definition": json.loads(w.definition),
                    "enabled": w.enabled,
                }
                for w in flows
            ],
            "runs": runs,
            "evidence": evidence,
            "catalog": CATALOG,
            "stopped": False,
            "connectors": [
                {
                    "id": "device",
                    "name": "Enrolled computer",
                    "category": "Local execution",
                    "status": "configured",
                    "description": "Computes approved workflows locally and sends signed outcomes. Provider credentials stay on your computer.",
                },
                *connectors,
            ],
        }

    @app.get("/api/automation/runs/{rid}")
    def detail(rid: str, uid=Depends(user)):
        with sessions() as db:
            job = db.scalar(select(Job).where(Job.id == rid, Job.account_id == uid))
            if not job:
                raise HTTPException(404)
            result = json.loads(job.result) if job.result else {}
            payload = json.loads(job.payload)
            decisions = db.scalars(
                select(ApprovalAudit)
                .where(ApprovalAudit.job_id == rid, ApprovalAudit.account_id == uid)
                .order_by(ApprovalAudit.created)
            ).all()
            trusted = [
                {
                    "seq": d.id,
                    "run_id": rid,
                    "step_id": d.step_id,
                    "kind": (
                        "cloud_operator_approved"
                        if d.approved
                        else "cloud_operator_rejected"
                    ),
                    "data": {
                        "actor": uid,
                        "note": d.note,
                        "source": "authenticated cloud approval",
                    },
                    "created": d.created,
                }
                for d in decisions
            ]
            return {
                "id": job.id,
                "workflow_id": job.workflow_id,
                "workflow": payload["workflow"],
                "inputs": payload["inputs"],
                "context": result.get("context", {}),
                "status": job.status,
                "cursor": result.get("cursor", 0),
                "error": result.get("error"),
                "created": job.created,
                "provenance": json.loads(job.result_proof or "{}"),
                "evidence": [
                    *trusted,
                    *[
                        {**e, "seq": str(i), "run_id": rid}
                        for i, e in enumerate(result.get("evidence", []))
                    ],
                ],
            }

    @app.post("/api/automation/connectors")
    def connector(uid=Depends(user)):
        raise HTTPException(
            409,
            "Configure universal connectors on the enrolled computer; credentials are never uploaded to the coordination cloud",
        )

    @app.post("/api/automation/plan")
    def plan(uid=Depends(user)):
        raise HTTPException(
            409,
            "Cloud AI is disabled on the $1 cost-target tier. Use local workflow design or an industry template.",
        )

    @app.post("/api/automation/stop")
    def stop(uid=Depends(user)):
        with sessions.begin() as db:
            for w in db.scalars(
                select(CloudWorkflow).where(CloudWorkflow.account_id == uid)
            ):
                w.enabled = False
            for j in db.scalars(
                select(Job).where(
                    Job.account_id == uid,
                    Job.status.in_(["queued", "waiting_approval"]),
                )
            ):
                j.status = "cancelled"
        return {
            "stopped": True,
            "note": "Work already executing on an offline device cannot be remotely undone. Revoke that device or stop it locally.",
        }

    @app.post("/api/automation/clear-stop")
    def clear(uid=Depends(user)):
        return {
            "stopped": False,
            "note": "Enable desired workflows individually; nothing restarts automatically",
        }

    @app.post("/v1/device/capabilities")
    def capabilities(body: Capabilities, identity=Depends(device)):
        uid, did = identity
        safe = []
        for entry in body.connectors:
            if not all(
                isinstance(entry.get(k), str) for k in ("id", "name", "base_url")
            ):
                raise HTTPException(400, "Invalid connector metadata")
            safe.append(
                {
                    k: entry.get(k, "")
                    for k in ("id", "name", "base_url", "protocol", "status")
                }
            )
        if len(json.dumps(safe).encode()) > 16384:
            raise HTTPException(413, "Capability metadata exceeds 16 KiB")
        with sessions.begin() as db:
            db.get(Device, did).capabilities = json.dumps(safe)
        return {"accepted": True}

    @app.post("/v1/device/claim")
    def claim(identity=Depends(device)):
        uid, did = identity
        now = time.time()
        with sessions.begin() as db:
            db.scalar(select(Account).where(Account.id == uid).with_for_update())
            # Lazily schedule the daily work when the user's device is available.
            for flow in db.scalars(
                select(CloudWorkflow)
                .where(
                    CloudWorkflow.account_id == uid,
                    CloudWorkflow.enabled.is_(True),
                    CloudWorkflow.next_run <= now,
                )
                .with_for_update()
            ):
                definition = json.loads(flow.definition)
                if definition["trigger"] != "schedule":
                    continue
                active = db.scalar(
                    select(Job.id)
                    .where(
                        Job.workflow_id == flow.id,
                        Job.status.in_(
                            ["queued", "running", "waiting_approval", "blocked"]
                        ),
                    )
                    .limit(1)
                )
                if not active:
                    enqueue(
                        db,
                        uid,
                        flow,
                        {},
                        "daily-"
                        + flow.id
                        + "-"
                        + datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    )
                flow.next_run = now + max(86400, definition["interval_seconds"])
            exhausted = db.scalars(
                select(Job)
                .where(
                    Job.account_id == uid,
                    Job.status == "running",
                    Job.lease_until < now,
                    Job.attempts >= 3,
                )
                .with_for_update()
            ).all()
            for old in exhausted:
                prior = (
                    json.loads(old.result)
                    if old.result
                    else {"cursor": 0, "context": {}}
                )
                prior["error"] = (
                    "Three device leases expired. Inspect the device and explicitly resume; external action outcomes may be uncertain."
                )
                old.result = json.dumps(prior)
                old.status = "blocked"
                old.updated = now
            candidates = (
                select(Job)
                .where(
                    Job.account_id == uid,
                    Job.attempts < 3,
                    or_(
                        Job.status == "queued",
                        and_(Job.status == "running", Job.lease_until < now),
                    ),
                )
                .order_by(Job.created)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            job = None
            capability_ids = {
                c["id"] for c in json.loads(db.get(Device, did).capabilities or "[]")
            }
            for candidate in db.scalars(candidates.limit(32)).all():
                required = {
                    step.get("connector_id")
                    for step in json.loads(candidate.payload)["workflow"]["steps"]
                    if step["kind"] == "connector"
                }
                if required.issubset(capability_ids):
                    job = candidate
                    break
            if not job:
                return {"job": None}
            job.status = "running"
            job.device_id = did
            job.lease_token = secrets.token_urlsafe(32)
            job.lease_until = now + 900
            job.attempts += 1
            job.updated = now
            return {
                "job": {
                    "id": job.id,
                    "payload": json.loads(job.payload),
                    "approved": json.loads(job.approved),
                    "previous_result": json.loads(job.result) if job.result else None,
                    "lease_token": job.lease_token,
                    "lease_until": job.lease_until,
                }
            }

    @app.post("/v1/device/jobs/{rid}/result")
    def result(rid: str, body: Result, request: Request, identity=Depends(device)):
        uid, did = identity
        encoded = body.model_dump_json(exclude={"lease_token"})
        size = len(encoded.encode())
        if size > 65536:
            raise HTTPException(413, "Result exceeds 64 KiB")
        with sessions.begin() as db:
            job = db.scalar(
                select(Job)
                .where(Job.id == rid, Job.account_id == uid)
                .with_for_update()
            )
            if (
                not job
                or job.device_id != did
                or not secrets.compare_digest(job.lease_token or "", body.lease_token)
            ):
                raise HTTPException(409, "Invalid result lease")
            definition = json.loads(job.payload)["workflow"]
            if body.cursor > len(definition["steps"]):
                raise HTTPException(400, "Run cursor exceeds workflow")
            if body.status == "completed":
                gated = {
                    s["id"]
                    for s in definition["steps"]
                    if s["kind"] in ("connector", "approval")
                }
                if (
                    body.cursor != len(definition["steps"])
                    or not gated.issubset(set(json.loads(job.approved)))
                    or any(s["id"] not in body.context for s in definition["steps"])
                ):
                    raise HTTPException(
                        400,
                        "Completion lacks required step outputs or cloud approval evidence",
                    )
            if body.status == "waiting_approval" and (
                body.cursor >= len(definition["steps"])
                or definition["steps"][body.cursor]["kind"]
                not in ("ai", "connector", "approval")
            ):
                raise HTTPException(400, "Invalid approval step")
            if job.status != "running":
                if job.result == encoded:
                    return {"accepted": True, "duplicate": True}
                raise HTTPException(409, "Result already recorded")
            if job.lease_until < time.time():
                raise HTTPException(
                    409, "Result lease expired; preserve local results and reclaim"
                )
            ledger = usage(db, uid)
            if ledger.bytes_used + size > MAX_MONTHLY_BYTES:
                raise HTTPException(429, "Monthly sync byte allowance reached")
            ledger.bytes_used += size
            job.result = encoded
            job.status = body.status
            job.updated = time.time()
            job.result_proof = json.dumps(
                {
                    "device_id": did,
                    "body_sha256": request.scope.get("hiyo_body_digest"),
                    "signature": request.headers.get("x-hiyo-signature"),
                    "timestamp": request.headers.get("x-hiyo-timestamp"),
                    "verified_at": time.time(),
                }
            )
        return {"accepted": True}

    @app.post("/internal/retention")
    def retention(request: Request):
        expected = os.environ.get("HIYO_MAINTENANCE_ACCOUNT", "")
        audience = os.environ.get("HIYO_SERVICE_URL", "")
        bearer = request.headers.get("authorization", "")
        if not expected or not audience or not bearer.startswith("Bearer "):
            raise HTTPException(403)
        try:
            from google.oauth2 import id_token
            from google.auth.transport.requests import Request as GoogleRequest

            claims = id_token.verify_oauth2_token(
                bearer[7:], GoogleRequest(), audience=audience
            )
            if claims.get("email") != expected or not claims.get("email_verified"):
                raise ValueError()
        except Exception as exc:
            raise HTTPException(403) from exc
        with sessions.begin() as db:
            expired = select(Job.id).where(Job.created < time.time() - 30 * 86400)
            db.execute(delete(ApprovalAudit).where(ApprovalAudit.job_id.in_(expired)))
            db.execute(delete(Job).where(Job.created < time.time() - 30 * 86400))
            db.execute(delete(Nonce).where(Nonce.expires < time.time()))
            db.execute(
                delete(EnrollmentTicket).where(EnrollmentTicket.expires < time.time())
            )
        return {"pruned": True}

    static = dashboard or os.environ.get("HIYO_DASHBOARD_DIR")
    if static and Path(static).is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="dashboard")
    return app
