from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import random
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)
from engineering_os.store import Store
from engineering_os.automation import Automation, Workflow, NoRedirect
from engineering_os.protocol import canonical


class OSKeyStore:
    @staticmethod
    def backend():
        import keyring

        candidate = keyring.get_keyring()
        candidates = getattr(candidate, "backends", [candidate])
        native = (
            "keyring.backends.Windows",
            "keyring.backends.macOS",
            "keyring.backends.SecretService",
            "keyring.backends.kwallet",
        )
        for backend in candidates:
            if type(backend).__module__.startswith(native) and backend.priority > 0:
                return backend
        raise RuntimeError(
            "A native OS credential store is required; plaintext and fallback backends are rejected"
        )

    def put(self, name, value):
        self.backend().set_password("Hiyo device signing keys", name, value)

    def get(self, name):
        value = self.backend().get_password("Hiyo device signing keys", name)
        if not value:
            raise RuntimeError("Device signing key is unavailable for this OS user")
        return value


class Agent:
    def __init__(self, home: Path, keys=None, transport=None):
        self.home = home.resolve()
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.keys = keys or OSKeyStore()
        self.transport = transport or self.http
        self.store = Store(self.home / "runtime")
        self.automation = Automation(self.store, provider="ollama")
        with self.store.db() as db:
            db.executescript(
                "CREATE TABLE IF NOT EXISTS cloud_jobs(job_id TEXT PRIMARY KEY, local_run TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0, resume_grant TEXT NOT NULL DEFAULT '');"
            )
        self.config_path = self.home / "device.json"

    @staticmethod
    def http(url, path, body, headers):
        parsed = urllib.parse.urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(
                "The coordination URL must use HTTPS without embedded credentials"
            )
        request = urllib.request.Request(
            url.rstrip("/") + path,
            data=body,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=30
        ) as response:
            raw = response.read(300 * 1024 + 1)
            if len(raw) > 300 * 1024:
                raise RuntimeError("Cloud response exceeds limit")
            return json.loads(raw)

    def enroll(self, ticket: dict, name: str):
        if self.config_path.exists():
            raise RuntimeError(
                "This device is already enrolled; revoke it deliberately before re-enrollment"
            )
        key = Ed25519PrivateKey.generate()
        public = base64.b64encode(
            key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode()
        pending = "pending-" + uuid.uuid4().hex
        self.keys.put(
            pending,
            base64.b64encode(
                key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            ).decode(),
        )
        response = self.transport(
            ticket["cloud_url"],
            "/v1/enroll",
            json.dumps(
                {"ticket": ticket["ticket"], "name": name, "public_key": public}
            ).encode(),
            {},
        )
        config = {
            "cloud_url": ticket["cloud_url"],
            "device_id": response["id"],
            "key_reference": pending,
        }
        fd = os.open(self.config_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(config, f)
        return {"device_id": response["id"], "default_sync": "daily"}

    def request(self, path, body):
        config = json.loads(self.config_path.read_text())
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        encoded = json.dumps(body, separators=(",", ":")).encode()
        raw = base64.b64decode(self.keys.get(config["key_reference"]))
        key = Ed25519PrivateKey.from_private_bytes(raw)
        signature = base64.b64encode(
            key.sign(canonical("POST", path, timestamp, nonce, encoded))
        ).decode()
        headers = {
            "X-Hiyo-Device": config["device_id"],
            "X-Hiyo-Timestamp": timestamp,
            "X-Hiyo-Nonce": nonce,
            "X-Hiyo-Signature": signature,
        }
        return self.transport(config["cloud_url"], path, encoded, headers)

    def process(self, job):
        if (self.home / "STOP").exists():
            return False
        with self.store.db() as db:
            existing = db.execute(
                "SELECT * FROM cloud_jobs WHERE job_id=?", (job["id"],)
            ).fetchone()
        if existing:
            rid = existing["local_run"]
        else:
            definition = Workflow.model_validate(job["payload"]["workflow"])
            # Every synced workflow uses the same bounded, non-shell local engine.
            wid = self.automation.workflow(definition)
            rid = self.automation.queue(wid, job["payload"]["inputs"])
            with self.store.db() as db:
                db.execute(
                    "INSERT INTO cloud_jobs(job_id,local_run,delivered) VALUES (?,?,0)",
                    (job["id"], rid),
                )
            prior = job.get("previous_result")
            if prior:
                self.automation.save_run(
                    rid, cursor=prior["cursor"], context=json.dumps(prior["context"])
                )
        with self.store.db() as db:
            run = dict(
                db.execute(
                    "SELECT * FROM automation_runs WHERE id=?", (rid,)
                ).fetchone()
            )
        previous_approved = json.loads(run["approved"])
        approved = list(dict.fromkeys(previous_approved + job.get("approved", [])))
        status = run["status"]
        grant = job["payload"].get("operator_resume", "")
        prior_grant = existing["resume_grant"] if existing else ""
        can_execute = status != "blocked" or bool(grant and grant != prior_grant)
        if status != "completed" and can_execute:
            if grant:
                with self.store.db() as db:
                    db.execute(
                        "UPDATE cloud_jobs SET resume_grant=? WHERE job_id=?",
                        (grant, job["id"]),
                    )
            self.automation.save_run(
                rid,
                status="approved" if approved else "queued",
                approved=json.dumps(approved),
            )
            self.automation.execute(rid)
        with self.store.db() as db:
            result = dict(
                db.execute(
                    "SELECT * FROM automation_runs WHERE id=?", (rid,)
                ).fetchone()
            )
            events = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM automation_evidence WHERE run_id=? ORDER BY seq DESC LIMIT 20",
                    (rid,),
                )
            ]
        evidence = []
        for event in events:
            data = json.loads(event["data"])
            if "output" in data:
                data["output"] = str(data["output"])[:1000]
            evidence.append(
                {
                    "step_id": event["step_id"],
                    "kind": event["kind"],
                    "data": data,
                    "created": event["created"],
                }
            )
        report = {
            "lease_token": job["lease_token"],
            "status": result["status"],
            "cursor": result["cursor"],
            "context": json.loads(result["context"]),
            "evidence": evidence,
            "error": result["error"],
        }
        if report["status"] not in (
            "completed",
            "waiting_approval",
            "blocked",
            "skipped",
        ):
            raise RuntimeError("Unexpected local workflow state")
        if len(json.dumps(report).encode()) > 65536:
            raise RuntimeError(
                "Result exceeds cloud quota; full evidence remains local for operator inspection"
            )
        # Failure preserves the local run. A future claim uploads the prior result without rerunning completed steps.
        self.request("/v1/device/jobs/" + job["id"] + "/result", report)
        with self.store.db() as db:
            db.execute("UPDATE cloud_jobs SET delivered=1 WHERE job_id=?", (job["id"],))
        return True

    def daily(self, max_jobs=32, max_seconds=1800):
        if (self.home / "STOP").exists():
            return {"status": "stopped", "processed": 0}
        # Reuse the proven advisory controller lock to prevent concurrent daily runs.
        from engineering_os.controller import Controller

        lock = Controller(self.store)
        lock.acquire()
        processed = 0
        began = time.monotonic()
        try:
            connectors = [
                {
                    k: c.get(k, "")
                    for k in ("id", "name", "base_url", "protocol", "status")
                }
                for c in self.automation.snapshot()["connectors"]
                if c.get("base_url")
            ]
            self.request("/v1/device/capabilities", {"connectors": connectors})
            while (
                processed < max_jobs
                and time.monotonic() - began < max_seconds
                and not (self.home / "STOP").exists()
            ):
                job = self.request("/v1/device/claim", {})["job"]
                if not job:
                    break
                if self.process(job):
                    processed += 1
            return {
                "status": "synced",
                "processed": processed,
                "elapsed_seconds": round(time.monotonic() - began, 2),
            }
        finally:
            if lock.lock:
                lock.lock.close()


def main():
    parser = argparse.ArgumentParser(description="Hiyo daily device agent")
    parser.add_argument("--home", type=Path, default=Path.home() / ".hiyo-device")
    sub = parser.add_subparsers(dest="command", required=True)
    enroll = sub.add_parser("enroll")
    enroll.add_argument("--ticket-file", type=Path, required=True)
    enroll.add_argument("--name", default="My computer")
    daily = sub.add_parser("daily")
    daily.add_argument("--jitter-seconds", type=int, default=0)
    sub.add_parser("stop")
    sub.add_parser("clear-stop")
    args = parser.parse_args()
    agent = Agent(args.home)
    if args.command == "enroll":
        print(
            json.dumps(
                agent.enroll(json.loads(args.ticket_file.read_text()), args.name)
            )
        )
    elif args.command == "daily":
        if args.jitter_seconds:
            threading.Event().wait(random.randint(0, min(args.jitter_seconds, 3600)))
        os.environ.setdefault("HIYO_AI_PROVIDER", "ollama")
        print(json.dumps(agent.daily()))
    elif args.command == "stop":
        (agent.home / "STOP").touch()
        agent.automation.stop()
    elif args.command == "clear-stop":
        (agent.home / "STOP").unlink(missing_ok=True)
        agent.automation.stop(False)


if __name__ == "__main__":
    main()
