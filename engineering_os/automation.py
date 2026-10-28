"""Cross-industry workflow engine. Local execution is real; provider actions are gated."""

from __future__ import annotations
import json
import os
import string
import threading
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error
import ipaddress
import re
import html
import xml.etree.ElementTree as ET
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from .store import Store

CATALOG = json.loads(
    Path(__file__).with_name("catalog.json").read_text(encoding="utf-8")
)


class Step(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,49}$")
    kind: Literal["transform", "condition", "ai", "approval", "record", "connector"]
    name: str = Field(min_length=1, max_length=150)
    template: str = Field(default="", max_length=10000)
    field: str = Field(default="", max_length=50)
    equals: str = Field(default="", max_length=1000)
    connector_id: str = Field(default="", max_length=60)
    method: Literal["GET", "POST", "PUT", "PATCH"] = "GET"
    path: str = Field(default="/", max_length=2000)


class Workflow(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=2000)
    industry: str = Field(default="general", pattern=r"^[a-z0-9-]{1,80}$")
    department: str = "Operations"
    trigger: Literal["manual", "webhook", "schedule"] = "manual"
    interval_seconds: int = Field(default=3600, ge=60, le=31536000)
    steps: list[Step] = Field(min_length=1, max_length=20)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_graph(self):
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Step IDs must be unique")
        return self


class RunInput(BaseModel):
    inputs: dict = Field(default_factory=dict)


class Decision(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=1000)


class WorkflowEnabled(BaseModel):
    enabled: bool


class ConnectorInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(max_length=2000)
    credential_variable: str = Field(
        default="", pattern=r"^(HIYO_CONNECTOR_[A-Z0-9_]+)?$"
    )
    auth: Literal["none", "bearer", "basic", "api_key"] = "bearer"
    protocol: Literal["rest", "graphql", "soap", "webhook"] = "rest"
    header_name: str = Field(
        default="X-API-Key", pattern=r"^[A-Za-z][A-Za-z0-9-]{0,49}$"
    )


class DiscoveryInput(BaseModel):
    approve_external_request: bool = False
    path: str = Field(default="/openapi.json", max_length=2000)


class PlanInput(BaseModel):
    goal: str = Field(min_length=10, max_length=10000)
    industry: str = Field(default="general", pattern=r"^[a-z0-9-]{1,80}$")
    department: str = Field(default="Operations", max_length=100)
    approve_paid_usage: bool = False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def bounded_template(template, values, limit=65536):
    """Substitute without constructing an unbounded intermediate string."""
    parts = []
    size = 0
    position = 0

    def add(value):
        nonlocal size
        text = str(value)
        size += len(text.encode())
        if size > limit:
            raise ValueError("Expanded template exceeds 64 KiB")
        parts.append(text)

    for match in string.Template.pattern.finditer(template):
        add(template[position : match.start()])
        key = match.group("named") or match.group("braced")
        if key is not None:
            if key not in values:
                raise KeyError(key)
            add(values[key])
        elif match.group("escaped") is not None:
            add("$")
        else:
            raise ValueError(
                "Invalid template placeholder; escape literal dollars as $$"
            )
        position = match.end()
    add(template[position:])
    return "".join(parts)


class Automation:
    def __init__(self, store: Store, provider=None):
        self.provider = provider or os.environ.get("HIYO_AI_PROVIDER", "ollama")
        self.store = store
        self.shutdown = threading.Event()
        with store.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, definition TEXT NOT NULL,
                enabled INTEGER NOT NULL, next_run REAL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_runs (
                id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(id),
                workflow TEXT NOT NULL, status TEXT NOT NULL, cursor INTEGER NOT NULL DEFAULT 0,
                inputs TEXT NOT NULL, context TEXT NOT NULL, approved TEXT NOT NULL DEFAULT '[]',
                error TEXT, created REAL NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_evidence (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                step_id TEXT, kind TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_connectors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, definition TEXT NOT NULL,
                last_success REAL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT OR IGNORE INTO automation_settings VALUES ('stopped','false');
            """)
            db.execute(
                "UPDATE automation_runs SET status='blocked', approved='[]', error='Interrupted execution; inspect evidence before explicitly resuming', updated=? WHERE status='running'",
                (time.time(),),
            )

    def audit(self, run_id, step_id, kind, **data):
        with self.store.db() as db:
            db.execute(
                "INSERT INTO automation_evidence(run_id,step_id,kind,data,created) VALUES (?,?,?,?,?)",
                (run_id, step_id, kind, json.dumps(data), time.time()),
            )

    def stopped(self):
        with self.store.db() as db:
            return (
                db.execute(
                    "SELECT value FROM automation_settings WHERE key='stopped'"
                ).fetchone()[0]
                == "true"
            )

    def stop(self, stopped=True):
        with self.store.db() as db:
            db.execute(
                "UPDATE automation_settings SET value=? WHERE key='stopped'",
                ("true" if stopped else "false",),
            )

    def workflow(self, definition: Workflow):
        wid = uuid.uuid4().hex[:12]
        with self.store.db() as db:
            db.execute(
                "INSERT INTO workflows VALUES (?,?,?,?,?,?)",
                (
                    wid,
                    definition.name,
                    definition.model_dump_json(),
                    int(definition.enabled),
                    (
                        time.time() + definition.interval_seconds
                        if definition.trigger == "schedule"
                        else None
                    ),
                    time.time(),
                ),
            )
        return wid

    def enable(self, wid, enabled):
        with self.store.db() as db:
            row = db.execute(
                "SELECT definition FROM workflows WHERE id=?", (wid,)
            ).fetchone()
            if not row:
                raise ValueError("Workflow not found")
            definition = json.loads(row[0])
            db.execute(
                "UPDATE workflows SET enabled=?, next_run=? WHERE id=?",
                (
                    int(enabled),
                    (
                        time.time() + definition["interval_seconds"]
                        if definition["trigger"] == "schedule"
                        else None
                    ),
                    wid,
                ),
            )

    def queue(self, wid, inputs):
        encoded = json.dumps(inputs)
        if len(encoded.encode()) > 65536:
            raise ValueError("Input exceeds 64 KiB")
        if any(
            not isinstance(k, str) or not k.isidentifier() or k.startswith("_")
            for k in inputs
        ):
            raise ValueError("Input keys must be simple identifiers")
        if self.stopped():
            raise ValueError("Automation emergency stop is active")
        with self.store.db() as db:
            row = db.execute("SELECT * FROM workflows WHERE id=?", (wid,)).fetchone()
            if not row:
                raise ValueError("Workflow not found")
            if not row["enabled"]:
                raise ValueError("Workflow is paused")
            rid = uuid.uuid4().hex[:12]
            now = time.time()
            db.execute(
                "INSERT INTO automation_runs(id,workflow_id,workflow,status,inputs,context,created,updated) VALUES (?,?,?,?,?,?,?,?)",
                (rid, wid, row["definition"], "queued", encoded, encoded, now, now),
            )
        self.audit(rid, None, "queued", source="approved workflow trigger")
        return rid

    def save_run(self, rid, **fields):
        allowed = {"status", "cursor", "context", "approved", "error"}
        if set(fields) - allowed:
            raise ValueError("Invalid run update")
        fields["updated"] = time.time()
        with self.store.db() as db:
            db.execute(
                "UPDATE automation_runs SET "
                + ",".join(k + "=?" for k in fields)
                + " WHERE id=?",
                (*fields.values(), rid),
            )

    @staticmethod
    def destination(base_url):
        url = urllib.parse.urlsplit(base_url)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.port not in (None, 443)
        ):
            raise ValueError(
                "Use an HTTPS base URL without credentials, query, fragment, or custom port"
            )
        host = url.hostname.lower()
        if host == "localhost" or host.endswith((".localhost", ".local")):
            raise ValueError("Loopback and local hostnames are not supported")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host:
                raise ValueError("Use a fully qualified hostname")
        else:
            if not address.is_global:
                raise ValueError(
                    "Private, reserved, and loopback IP addresses are not supported"
                )
        return host

    def connector(self, definition: ConnectorInput):
        self.destination(definition.base_url)
        if definition.auth != "none" and not definition.credential_variable:
            raise ValueError("Choose a scoped credential variable, not a secret value")
        if definition.header_name.lower() in (
            "host",
            "authorization",
            "cookie",
            "proxy-authorization",
            "content-length",
            "connection",
        ):
            raise ValueError("Reserved authentication header name")
        cid = uuid.uuid4().hex[:12]
        with self.store.db() as db:
            db.execute(
                "INSERT INTO automation_connectors VALUES (?,?,?,?,?)",
                (cid, definition.name, definition.model_dump_json(), None, time.time()),
            )
        return cid

    def connector_status(self, row):
        definition = json.loads(row["definition"])
        host = self.destination(definition["base_url"])
        allowed = {
            h.strip().lower()
            for h in os.environ.get("HIYO_CONNECTOR_HOSTS", "").split(",")
            if h.strip()
        }
        bound = definition["auth"] == "none" or bool(
            os.environ.get(definition["credential_variable"])
        )
        return dict(
            id=row["id"],
            name=row["name"],
            category="Custom API",
            base_url=definition["base_url"],
            credential_variable=definition["credential_variable"],
            host_allowed=host in allowed,
            credential_present=bound,
            status=(
                "verified"
                if row["last_success"] and host in allowed and bound
                else (
                    "configured" if host in allowed and bound else "needs_configuration"
                )
            ),
            protocol=definition.get("protocol", "rest"),
            last_success=row["last_success"],
            description="Universal HTTPS connector (REST, GraphQL, SOAP, webhooks). Every external action requires explicit approval. Endpoint schemas and provider permissions are configured per workflow.",
        )

    def request_connector(self, step, context, text, discovery=False):
        with self.store.db() as db:
            row = db.execute(
                "SELECT * FROM automation_connectors WHERE id=?",
                (step["connector_id"],),
            ).fetchone()
        if not row:
            raise ValueError("Connector not found")
        state = self.connector_status(row)
        if not state["host_allowed"]:
            raise RuntimeError(
                "Connector host is not in the operator-managed HIYO_CONNECTOR_HOSTS allowlist"
            )
        if not state["credential_present"]:
            raise RuntimeError(
                "Connector credential binding is missing; configure its scoped variable securely"
            )
        definition = json.loads(row["definition"])
        host = self.destination(definition["base_url"])
        escaped = {k: urllib.parse.quote(str(v), safe="") for k, v in context.items()}
        path = bounded_template(step.get("path", "/"), escaped, 2000)
        if not path.startswith("/") or path.startswith("//") or "\\" in path:
            raise ValueError(
                "Connector endpoint must be an absolute path on the configured host"
            )
        url = definition["base_url"].rstrip("/") + path
        if self.destination(url.split("?", 1)[0]) != host:
            raise ValueError("Connector destination changed")
        headers = {"Accept": "application/json"}
        if definition["auth"] != "none":
            credential = os.environ[definition["credential_variable"]]
            if definition["auth"] == "api_key":
                headers[definition["header_name"]] = credential
            else:
                headers["Authorization"] = (
                    "Bearer " if definition["auth"] == "bearer" else "Basic "
                ) + credential
        payload = None
        protocol = definition.get("protocol", "rest")
        if (
            not discovery
            and protocol in ("graphql", "soap", "webhook")
            and step["method"] != "POST"
        ):
            raise ValueError("GraphQL, SOAP and webhook actions require POST")
        if step["method"] != "GET":
            values = {k: str(v) for k, v in context.items()}
            if protocol == "soap":
                if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
                    raise ValueError("XML entities and DTDs are forbidden")
                rendered = bounded_template(
                    text, {k: html.escape(v, quote=True) for k, v in values.items()}
                )
                ET.fromstring(rendered)
                payload = rendered.encode()
                headers["Content-Type"] = "application/soap+xml; charset=utf-8"
            else:

                def interpolate(value):
                    if isinstance(value, str):
                        return bounded_template(value, values)
                    if isinstance(value, list):
                        return [interpolate(x) for x in value]
                    if isinstance(value, dict):
                        return {k: interpolate(v) for k, v in value.items()}
                    return value

                body = interpolate(json.loads(text or "{}"))
                if protocol == "graphql" and (
                    not isinstance(body, dict) or not isinstance(body.get("query"), str)
                ):
                    raise ValueError(
                        "GraphQL actions require a JSON query and optional variables"
                    )
                payload = json.dumps(body).encode()
                headers["Content-Type"] = "application/json"
        if payload is not None and len(payload) > 65536:
            raise ValueError("Mapped request body exceeds 64 KiB")
        request = urllib.request.Request(
            url, data=payload, headers=headers, method=step["method"]
        )
        try:
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(request, timeout=30) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Connector response exceeds 64 KiB")
                if protocol == "soap":
                    xml = raw.decode("utf-8")
                    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
                        raise ValueError("XML entities and DTDs are forbidden")
                    ET.fromstring(xml)
                    result = {"xml": xml}
                else:
                    result = (
                        json.loads(raw)
                        if raw.strip()
                        else {"http_status": response.status}
                    )
        except Exception as exc:
            raise RuntimeError(
                "Connector request failed; redirects are denied. Check provider permissions, endpoint schema, network policy and TLS trust."
            ) from exc
        with self.store.db() as db:
            db.execute(
                "UPDATE automation_connectors SET last_success=? WHERE id=?",
                (time.time(), row["id"]),
            )
        return json.dumps(result, ensure_ascii=False)

    def ai(self, prompt):
        if self.provider == "ollama":
            payload = json.dumps(
                {
                    "model": os.environ.get("HIYO_LOCAL_MODEL", "llama3.2:3b"),
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 800},
                }
            ).encode()
            request = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.build_opener(
                    urllib.request.ProxyHandler({}), NoRedirect()
                ).open(request, timeout=30) as response:
                    raw = response.read(1024 * 1024 + 1)
                    if len(raw) > 1024 * 1024:
                        raise RuntimeError("Local model response exceeds limit")
                    data = json.loads(raw)
                if not isinstance(data.get("response"), str):
                    raise ValueError("No local model output")
                return data["response"], {
                    "provider": "local",
                    "input_tokens": data.get("prompt_eval_count"),
                    "output_tokens": data.get("eval_count"),
                }
            except Exception as exc:
                raise RuntimeError(
                    "Local Ollama model unavailable; no paid cloud fallback was attempted"
                ) from exc
        key = os.environ.get("HIYO_AI_API_KEY")
        if not key:
            raise RuntimeError(
                "OpenAI connector is not configured: add HIYO_AI_API_KEY securely in environment settings"
            )
        # Fixed destination, inherited proxy and verified TLS. No user-selected URLs or tools.
        payload = json.dumps(
            {
                "model": os.environ.get("HIYO_AI_MODEL", "gpt-4.1-mini"),
                "input": prompt,
                "max_output_tokens": 800,
            }
        ).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=payload,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.build_opener(NoRedirect()).open(
                req, timeout=30
            ) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise RuntimeError("Provider response too large")
                data = json.loads(raw)
        except Exception as exc:
            # Never persist HTTP headers, secret bindings, or raw provider error bodies.
            raise RuntimeError(
                "AI provider request failed; inspect network policy, authorization, and provider availability"
            ) from exc
        text = "\n".join(
            part["text"]
            for item in data.get("output", [])
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        )
        if not text:
            raise RuntimeError("AI provider returned no text output")
        return text, data.get("usage", {})

    def execute(self, rid):
        if self.stopped():
            return
        with self.store.db() as db:
            claimed = db.execute(
                "UPDATE automation_runs SET status='running',updated=? WHERE id=? AND status IN ('queued','approved','blocked')",
                (time.time(), rid),
            ).rowcount
            if not claimed:
                return
            row = dict(
                db.execute(
                    "SELECT * FROM automation_runs WHERE id=?", (rid,)
                ).fetchone()
            )
        definition = json.loads(row["workflow"])
        context = json.loads(row["context"])
        approved = json.loads(row["approved"])
        started = time.monotonic()
        for index, step in enumerate(
            definition["steps"][row["cursor"] :], start=row["cursor"]
        ):
            if (
                self.shutdown.is_set()
                or self.stopped()
                or time.monotonic() - started > 120
            ):
                self.save_run(
                    rid,
                    status="blocked",
                    error="Stopped or run time limit reached",
                    cursor=index,
                )
                return
            sid = step["id"]
            kind = step["kind"]
            needs_approval = kind in ("approval", "connector") or (
                kind == "ai" and self.provider != "ollama"
            )
            if needs_approval and sid not in approved:
                self.save_run(rid, status="waiting_approval", cursor=index, error=None)
                self.audit(
                    rid,
                    sid,
                    "approval_required",
                    name=step["name"],
                    paid_service=kind == "ai" and self.provider != "ollama",
                    external_action=kind == "connector",
                    message=step.get("template", ""),
                    destination=step.get("connector_id", ""),
                    method=step.get("method", "GET"),
                    path=step.get("path", "/"),
                )
                return
            try:
                text = (
                    step.get("template", "")
                    if kind == "connector"
                    else bounded_template(
                        step.get("template", ""),
                        {k: str(v) for k, v in context.items()},
                    )
                )
                if len(text.encode()) > 65536:
                    raise ValueError("Step input exceeds 64 KiB")
                usage = {}
                if kind == "condition":
                    output = str(context.get(step.get("field"), "")) == step.get(
                        "equals", ""
                    )
                    if not output:
                        self.audit(
                            rid, sid, "condition_not_matched", field=step.get("field")
                        )
                        self.save_run(
                            rid, status="skipped", cursor=index + 1, error=None
                        )
                        return
                elif kind == "ai":
                    output, usage = self.ai(text)
                elif kind == "connector":
                    output = self.request_connector(step, context, text)
                elif kind == "approval":
                    output = "Approved by the authenticated operator"
                else:
                    output = text
                if len(str(output).encode()) > 65536:
                    raise ValueError("Step output exceeds 64 KiB")
                context[sid] = output
                self.audit(
                    rid,
                    sid,
                    "step_completed",
                    name=step["name"],
                    action_kind=kind,
                    output=output,
                    usage=usage,
                )
                self.save_run(
                    rid, cursor=index + 1, context=json.dumps(context), error=None
                )
            except Exception as exc:
                self.audit(rid, sid, "step_blocked", error=str(exc))
                self.save_run(
                    rid,
                    status="blocked",
                    error=str(exc),
                    cursor=index,
                    approved=(
                        json.dumps([x for x in approved if x != sid])
                        if kind in ("ai", "connector")
                        else json.dumps(approved)
                    ),
                )
                return
        self.save_run(rid, status="completed", error=None)
        self.audit(rid, None, "completed", steps=len(definition["steps"]))

    def decide(self, rid, approve, note):
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM automation_runs WHERE id=?", (rid,)
            ).fetchone()
            if not row or row["status"] != "waiting_approval":
                raise ValueError("Run is not awaiting approval")
            definition = json.loads(row["workflow"])
            sid = definition["steps"][row["cursor"]]["id"]
            approved = json.loads(row["approved"])
            if approve:
                approved.append(sid)
            db.execute(
                "UPDATE automation_runs SET status=?,approved=?,updated=? WHERE id=?",
                (
                    "approved" if approve else "cancelled",
                    json.dumps(approved),
                    time.time(),
                    rid,
                ),
            )
        self.audit(
            rid,
            sid,
            "approved" if approve else "rejected",
            note=note,
            actor="authenticated operator",
        )
        if approve:
            self.execute(rid)

    def tick(self, now=None):
        if self.shutdown.is_set() or self.stopped():
            return []
        now = now or time.time()
        due = []
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            for row in db.execute(
                "SELECT * FROM workflows WHERE enabled=1 AND next_run<=?", (now,)
            ).fetchall():
                definition = json.loads(row["definition"])
                db.execute(
                    "UPDATE workflows SET next_run=? WHERE id=?",
                    (now + definition["interval_seconds"], row["id"]),
                )
                pending = db.execute(
                    "SELECT 1 FROM automation_runs WHERE workflow_id=? AND status IN ('queued','running','waiting_approval','approved','blocked')",
                    (row["id"],),
                ).fetchone()
                if not pending:
                    due.append(row["id"])
        runs = []
        for wid in due:
            try:
                rid = self.queue(wid, {})
                self.execute(rid)
                runs.append(rid)
            except ValueError:
                pass
        return runs

    def loop(self):
        while not self.shutdown.wait(1):
            try:
                self.tick()
            except Exception:
                # Preserve queue state and stop scheduling on unexpected persistence errors.
                self.shutdown.set()

    def snapshot(self):
        with self.store.db() as db:
            workflows = [
                dict(r)
                for r in db.execute("SELECT * FROM workflows ORDER BY created DESC")
            ]
            runs = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM automation_runs ORDER BY created DESC LIMIT 200"
                )
            ]
            events = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM automation_evidence ORDER BY seq DESC LIMIT 400"
                )
            ]
            custom = [
                self.connector_status(dict(r))
                for r in db.execute(
                    "SELECT * FROM automation_connectors ORDER BY created DESC"
                )
            ]
        for w in workflows:
            w["definition"] = json.loads(w["definition"])
            w["enabled"] = bool(w["enabled"])
        for r in runs:
            for k in ["workflow", "inputs", "context", "approved"]:
                r[k] = json.loads(r[k])
        for e in events:
            e["data"] = json.loads(e["data"])
        return dict(
            workflows=workflows,
            runs=runs,
            evidence=events,
            stopped=self.stopped(),
            catalog=CATALOG,
            ai_provider=self.provider,
            connectors=[
                {
                    "id": "local",
                    "name": "Hiyo workspace",
                    "category": "Data & operations",
                    "status": "ready",
                    "description": "Local transformations, conditions, approvals, and persistent records.",
                },
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "category": "AI intelligence",
                    "status": (
                        "configured"
                        if os.environ.get("HIYO_AI_API_KEY")
                        else "needs_configuration"
                    ),
                    "description": "Responses API adapter. Each paid AI step requires explicit approval; live provider validation is still required.",
                },
                *[
                    {
                        "id": name.lower().replace(" ", "-"),
                        "name": name,
                        "category": category,
                        "status": "configurable",
                        "description": "Connect through the HTTPS API adapter using the provider endpoint and an operator-managed credential binding. Native OAuth and domain-specific actions are not implemented.",
                    }
                    for name, category in [
                        ("Google Workspace", "Productivity"),
                        ("Microsoft 365", "Productivity"),
                        ("Slack", "Communication"),
                        ("Shopify", "Commerce"),
                        ("Salesforce", "CRM"),
                        ("HubSpot", "CRM"),
                        ("Stripe", "Finance"),
                        ("WhatsApp Business", "Communication"),
                        ("SAP", "Enterprise ERP"),
                    ]
                ],
                *custom,
            ],
        )


def automation_router(engine: Automation):
    router = APIRouter(prefix="/api/automation")

    @router.get("/state")
    def state():
        return engine.snapshot()

    @router.post("/workflows")
    def create(body: Workflow):
        return {"id": engine.workflow(body)}

    @router.post("/templates/{tid}")
    def template(tid: str):
        t = next((t for t in CATALOG["templates"] if t["id"] == tid), None)
        if not t:
            raise HTTPException(404, "Template not found")
        return {
            "id": engine.workflow(
                Workflow(**{k: v for k, v in t.items() if k not in ("id", "example")})
            )
        }

    @router.post("/workflows/{wid}/enabled")
    def enabled(wid: str, body: WorkflowEnabled):
        try:
            engine.enable(wid, body.enabled)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"enabled": body.enabled}

    @router.post("/workflows/{wid}/trigger")
    def trigger(wid: str, body: RunInput):
        try:
            rid = engine.queue(wid, body.inputs)
            engine.execute(rid)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"id": rid}

    @router.post("/runs/{rid}/decision")
    def decide(rid: str, body: Decision):
        try:
            engine.decide(rid, body.approve, body.note)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "decision recorded"}

    @router.post("/runs/{rid}/resume")
    def resume(rid: str):
        with engine.store.db() as db:
            row = db.execute(
                "SELECT status FROM automation_runs WHERE id=?", (rid,)
            ).fetchone()
        if not row or row["status"] != "blocked":
            raise HTTPException(409, "Only blocked runs can be explicitly resumed")
        engine.execute(rid)
        return {"status": "resume requested"}

    @router.post("/connectors")
    def connector(body: ConnectorInput):
        try:
            return {"id": engine.connector(body)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/connectors/{cid}/discover")
    def discover(cid: str, body: DiscoveryInput):
        if not body.approve_external_request:
            raise HTTPException(
                400, "Approve the read-only provider discovery request first"
            )
        with engine.store.db() as db:
            row = db.execute(
                "SELECT * FROM automation_connectors WHERE id=?", (cid,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "Connector not found")
        definition = json.loads(row["definition"])
        protocol = definition.get("protocol", "rest")
        if protocol == "webhook":
            return {
                "protocol": protocol,
                "operations": [
                    {
                        "method": "POST",
                        "path": body.path,
                        "summary": "User-configured outbound webhook",
                    }
                ],
                "discovered": False,
            }
        step = {
            "connector_id": cid,
            "method": "POST" if protocol == "graphql" else "GET",
            "path": body.path,
        }
        query = (
            json.dumps(
                {"query": "{ __schema { queryType { name } mutationType { name } } }"}
            )
            if protocol == "graphql"
            else "{}"
        )
        try:
            result = json.loads(
                engine.request_connector(step, {}, query, discovery=True)
            )
            if protocol == "rest":
                operations = [
                    {
                        "method": method.upper(),
                        "path": path,
                        "summary": operation.get(
                            "summary", operation.get("operationId", "")
                        ),
                    }
                    for path, item in result.get("paths", {}).items()
                    for method, operation in item.items()
                    if method.lower() in ("get", "post", "put", "patch")
                    and isinstance(operation, dict)
                ][:200]
            elif protocol == "soap":
                operations = [
                    {
                        "method": "POST",
                        "path": body.path.split("?", 1)[0],
                        "summary": node.attrib.get("name", ""),
                    }
                    for node in ET.fromstring(result["xml"]).iter()
                    if node.tag.split("}")[-1] == "operation"
                ][:200]
            else:
                operations = [
                    {
                        "method": "POST",
                        "path": body.path,
                        "schema": result.get("data", {}),
                    }
                ]
            return {"protocol": protocol, "operations": operations, "discovered": True}
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/plan")
    def plan(body: PlanInput):
        if engine.provider != "ollama" and not body.approve_paid_usage:
            raise HTTPException(400, "Explicit paid AI usage approval is required")
        prompt = (
            "Design a business automation workflow. Return ONLY a JSON object with name, description, industry, department, trigger=manual, interval_seconds=3600, enabled=true, and steps. Each step has id (simple identifier), kind (transform, condition, ai, approval, record), name, template. Templates use $variable syntax; initial inputs are name, company and request. Only reference prior step IDs. Put a human approval before the final record. Do not create purchases, external communications, credential changes, deployments, regulated decisions, or destructive actions. Do not invent integrations. Industry: "
            + body.industry
            + "; department: "
            + body.department
            + "; goal: "
            + body.goal
        )
        try:
            text, usage = engine.ai(prompt)
            proposed = Workflow.model_validate_json(text)
            if any(s.kind == "connector" for s in proposed.steps):
                raise ValueError("Connector actions require explicit manual setup")
            return {"workflow": proposed.model_dump(), "usage": usage, "saved": False}
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post("/stop")
    def stop():
        engine.stop()
        return {"stopped": True}

    @router.post("/clear-stop")
    def clear():
        engine.stop(False)
        return {"stopped": False}

    return router
