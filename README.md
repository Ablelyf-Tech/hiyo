# Hiyo — AI Automation OS

**One intelligence engine for every industry and department.** Hiyo coordinates business workflows, connects existing systems through a universal HTTPS connector, and runs approved work on the user's computer. GCP hosts account identity, coordination, signed sync, usage accounting and the dashboard. Autonomous engineering remains an optional local module.

This source release includes executable local workflows, a private API/dashboard, a PostgreSQL cloud coordination service, a signed daily device agent and reviewable GCP infrastructure. **Production deployment is deliberately deferred. Capacity for 100,000 accounts and a $1/user/month total cloud cost are targets, not verified production claims.** See [production gates](docs/PRODUCTION.md) and [unit economics](docs/UNIT_ECONOMICS.md).

## What is implemented

- Visual workflow builder: transformations, conditions, local AI, human approvals, connected-system actions, saved outcomes, manual/API triggers and schedules.
- Ten starting industry categories, eight departments and fourteen adaptable workflow templates. Custom industry identifiers are supported; templates are starting points, not certified regulated-domain decisions.
- **Hiyo Universal Connector**: REST/JSON, GraphQL, SOAP/XML and outbound webhooks; scoped environment-bound authentication; schema discovery; data mapping; destination allowlists; explicit external-action approvals. HubSpot, SAP OData and other compatible APIs use this same layer. It does not magically connect inaccessible systems or implement every provider's OAuth/schema semantics.
- **Local-first AI** via an already-installed Ollama model. A separately approved OpenAI adapter exists for the private local app. The cloud-sync device tier uses local models with no paid cloud-model fallback.
- Cloud account isolation, Firebase identity verification, device enrollment/revocation, Ed25519 signatures, replay protection, leased jobs, idempotent results, approval gates, retention and usage quotas.
- A daily Windows agent: processes approved jobs locally and syncs signed results to its account dashboard. Offline work stays queued.
- GCP Cloud Run, regional PostgreSQL, Secret Manager, IAM, Artifact Registry, retention scheduling and budget-alert Terraform.
- Engineering controller: Codex roles, persistent SQLite queue, tests/review, retries, Git checkpoints, STOP and delivery artifacts. See [engineering module](docs/ENGINEERING.md).

## View the product

The [GitHub Pages preview](https://ablelyf-tech.github.io/hiyo/) uses browser-only storage. Its banner identifies sample content; local transformations and approval flows actually execute in the browser, while AI and remote connectors remain unavailable there. Publishing source is `gh-pages` → `/ (root)` in [Pages settings](https://github.com/Ablelyf-Tech/hiyo/settings/pages). A branch push is not proof Pages is enabled.

## Windows local installation

Prerequisites: Windows 10/11, Python 3.11+, Git and Node.js 22+. Use their official installers.

```powershell
git clone https://github.com/Ablelyf-Tech/hiyo.git
cd hiyo
.\scripts\install.ps1
.\scripts\start.ps1 -ProjectsRoot C:\Projects
```

Open the local app at port 8787. Its access token is stored in `%LOCALAPPDATA%\Hiyo\dashboard-token`; read it locally and never publish it. The API binds to loopback. The default surface is the business platform; **Engineering module** opens the coding controller. To use local AI, install Ollama and a suitable model separately; Hiyo never silently downloads a model or falls back to paid inference. Set `HIYO_LOCAL_MODEL` if using a different local model.

Linux/cloud development: run `./scripts/setup.sh`, then:

```bash
.venv/bin/python -m engineering_os.cli --home /workspace/hiyo-state serve \
  --projects-root /workspace/projects --dashboard /workspace/hiyo/dashboard/dist
```

## Daily computer processing

After a future GCP deployment, sign in to the cloud dashboard and choose **Enroll computer**. Download the one-use, 15-minute enrollment ticket privately. On that computer:

```powershell
.\scripts\install-device.ps1 -TicketFile C:\Private\hiyo-enrollment.json -DeviceName 'My work computer'
```

This explicitly enrolls the device and registers **Hiyo Daily Device Sync**, default 09:00 local time with up to one hour of jitter. Keys use the OS credential store. The user must be logged in and the computer available; missed jobs remain queued. The daily run handles at most 32 jobs and 30 minutes of processing. Full operating details: [device agent](docs/DEVICE.md).

## Cloud deployment — later

Cloud backend entry point: `hiyo_cloud.factory:app`. Container: `Dockerfile.cloud`. Infrastructure: `infra/gcp/`.

No cloud project, billable resource, database, identity provider or production service has been created. Follow [PRODUCTION.md](docs/PRODUCTION.md) for secret setup, migration, Firebase configuration, load tests, backups and release approval. Do not treat `terraform validate` or local SQLite-backed cloud tests as a PostgreSQL capacity test.

## Cost target

The included usage profile reserves an estimated $0.25/account/month plus $0.0005/job, with at most 1,000 jobs, 64 MiB combined sync/dashboard bytes and 10,000 authenticated requests per month. Cloud paid AI is disabled. These are **application reservations and quotas, not real GCP billing measurements or a guaranteed invoice cap**. GCP budgets alert; they do not stop every charge. Device electricity, hardware and third-party licensing are not paid by Hiyo. See [cost model and launch gates](docs/UNIT_ECONOMICS.md).

## Tests

```bash
.venv/bin/python -m pytest -q
cd dashboard
npm test
npm run build
```

Build modes: normal private application; `VITE_DEMO_MODE=true` for Pages; `VITE_CLOUD_MODE=true` with Firebase public configuration for cloud sign-in. Never set both flags. [Validation record](docs/VALIDATION.md) distinguishes test fixtures, real local executions, unrun provider checks and production limitations.

More: [product model](docs/PRODUCT.md) · [architecture](docs/ARCHITECTURE.md) · [universal connector](docs/UNIVERSAL_CONNECTOR.md) · [security](docs/SECURITY.md).
