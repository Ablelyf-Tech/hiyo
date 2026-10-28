# Hiyo architecture

```text
Firebase-authenticated browser
        |
Cloud Run coordination API ── Cloud SQL PostgreSQL
        |                       accounts, definitions, jobs, leases,
        |                       decisions, replay nonces and usage ledger
        |
Ed25519 signed device claim/result API
        |
Daily user-computer agent ── native OS key store
        |
Local SQLite workflow engine ── local Ollama / universal HTTPS connector
        |
approved local work → signed result → account dashboard
```

The local private API (`engineering_os/api.py`) serves the full business UI and optional engineering module. It uses SQLite and a local access token for a trusted single operator. This local API is not the 100,000-account cloud service.

The cloud API (`hiyo_cloud/app.py`) requires PostgreSQL in normal production startup. SQLite is accepted only through an explicit test/development factory argument. Firebase verifies audience, issuer, expiry, signature and verified nonanonymous identity. Every business query filters by the authenticated account; device endpoints verify possession of an enrolled Ed25519 key, timestamps, persistent nonces, account state and revocation. Current SQL protection is application-level account scoping, not database row-level security.

Cloud SQL uses bounded connection pools (5 per container, at most 20 configured Cloud Run instances), idempotency constraints, indexed account/status/created queries and row locks with SKIP LOCKED for claims. Account/month usage is serialized before job reservation. In-flight jobs have 15-minute leases and at most three automatic claims. Inspect uncertain/blocked work before an explicit resume. Signed device outcomes establish provenance, not a formal proof that an operator-controlled device is honest.

Cloud paid-model inference is disabled for the $1 cost-target device tier. Definitions and payloads are bounded (16 KiB definition, 128 KiB job, 64 KiB result, 20 steps). Agent credentials never become cloud workflow inputs. Only connector metadata is synced. Requests use verified TLS and deny cross-host redirects. The universal connector permits only operator-allowlisted destinations; external requests require approval.

The browser public preview is a separate build-time mode with browser-only storage. It never accesses the private controller or remote model/business APIs. Cloud mode uses Firebase browser authentication. The three builds share presentation and workflow definitions, not authentication bypasses.

Engineering workers retain their separate Codex sandbox and approved acceptance-runner model; see ENGINEERING.md. Live processes do not survive snapshots. No Git worktree is needed during cloud onboarding.
