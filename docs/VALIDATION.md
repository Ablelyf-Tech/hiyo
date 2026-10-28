# Validation record — Hiyo 0.2.0

Validated in the managed Linux workspace on 28 October 2026. No GCP deployment, production-capacity result or measured $1 invoice is claimed.

| Check | Observed result |
| --- | --- |
| Backend suite | **45 passed**, no failed or skipped tests; one upstream Starlette/httpx deprecation warning |
| Frontend suite | **11 passed**, no failed or skipped tests |
| Dashboard builds | Private, public preview and cloud-auth build modes pass |
| Local workflow engine | Real transformations, conditions, approval/resume, scheduling, evidence and STOP behavior pass |
| Universal connector | Destination/credential gates and JSON-injection prevention pass; GraphQL and SOAP adapter tests use explicit provider response fixtures; DTD rejection passes |
| Local AI fallback policy | An unavailable local model blocks; no paid provider fallback is attempted |
| Cloud coordination | Account isolation, idempotent job creation/results, device claims, expiry/replay/revocation, quota and completion-approval gates pass |
| Device sync integration | One-use enrollment → real Ed25519 signatures → local transformation run → result upload → account dashboard detail passes against an in-process cloud API, using a memory key-store fixture |
| Engineering module | Existing scheduler, Codex subprocess-contract fixture, Git checkpoint/artifact, failure and stop tests remain passing |
| Private app browser/API | Token login → industry template → real SQLite workflow → human approval → completed outcome passes against a local server |
| Browser preview smoke | Industry template → local browser run → approval → completed evidence; universal connector dialog; 390px layout without overflow; zero private API requests and page JavaScript errors in public preview |
| Terraform | Official Terraform download checksum verified; provider initialization and **terraform validate pass**; no plan/apply or GCP resource created |
| Python/source | Compilation and dependency installation pass; exact development and Linux cloud runtime locks saved |

## Explicitly unrun

- Real Firebase identity provider, GCP deployment, Cloud SQL/PostgreSQL locking and failover, production backup/restore, staged scale/load tests and actual billing measurements.
- A 100,000-account production workload, 100,000 concurrent users or a guaranteed $1/account/month cloud invoice.
- Native Windows installation, Task Scheduler, Windows Credential Manager, signed desktop distribution and real Ollama model inference.
- Live HubSpot, SAP or other vendor APIs/OAuth permissions. Adapter tests use named fixtures; they are not provider certifications.
- Live Codex model completion: an earlier read-only smoke was blocked by cloud proxy HTTP 403 for chatgpt.com. The existing environment draft preserves the pending network addition. No fabricated successful model result is reported.
- Docker image build, container vulnerability scan or Artifact Registry publication.

SQLite-backed cloud API tests prove the tested protocol and account behavior; they do not prove PostgreSQL concurrency or deployed capacity. See PRODUCTION.md for release gates and UNIT_ECONOMICS.md for cost assumptions. Deployment remains deferred by the user.
