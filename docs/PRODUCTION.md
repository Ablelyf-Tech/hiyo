# Production deployment and 100,000-account validation

**Deployment is deferred at the user's request.** No GCP project, billable resource or live service was created. This repository is an implementation and infrastructure handoff; it is not a declaration of production certification.

## Capacity target

100,000 enrolled accounts doing staggered daily local processing. This does not assert 100,000 simultaneous cloud AI tasks or 100,000 concurrent interactive sessions. Cloud Run is capped at 20 instances × 40 request concurrency, with 5 SQL connections/container and a 200-connection regional PostgreSQL configuration. These are starting parameters for testing, not proven capacity numbers.

## Prepare before deployment

- Choose the GCP project, region, billing account, production identity domain, and accountable operators.
- Use encrypted, access-restricted remote Terraform state. The database password is a sensitive input and still exists in Terraform state; protect it accordingly.
- Enable Firebase/Identity Platform authentication and Google sign-in; authorize only the actual dashboard domains. Verify disabled-user and revocation behavior and decide the acceptable ID-token lifetime/revocation horizon.
- Review IAM, app account scoping, secret rotation, audit policy, backups and restore procedures. Application-level account filters are implemented; PostgreSQL RLS and organizational team RBAC are not.
- Build the container with the public Firebase web config. API key/config values for Firebase web auth are public identifiers, not a replacement for server token verification or domain restrictions.
- Review the Terraform plan and explicitly approve billable production resources. Do not run apply from an unreviewed script.

## Infrastructure and release order

1. Use Terraform to provision the reviewed Artifact Registry, Cloud SQL database/user and Secret Manager secret metadata. The initial plan cannot start the API until the database URL secret version exists.
2. Add `HIYO_DATABASE_URL` securely to the secret, URL-encoding the database password. With the Cloud Run SQL volume it has the form `postgresql+psycopg://hiyo_app:<encoded-secret>@/hiyo?host=/cloudsql/<connection-name>`. Never commit the value or pass it through chat.
3. Build/scan `Dockerfile.cloud` and publish a reviewed image to Artifact Registry, pinned by digest for production. Docker build/publication has not been run here.
4. Run `python -m hiyo_cloud.migrate` as a controlled job using the database binding. It initializes the first schema; future changes need reviewed versioned migrations. Do not rely on per-instance create_all during live API startup.
5. Deploy Cloud Run with the bound secret and least-privilege service account. Set `HIYO_FIREBASE_PROJECT` and the actual HTTPS `HIYO_SERVICE_URL` before enabling device enrollment and maintenance. Terraform initially allows a blank service URL for first provisioning; update it after obtaining the service URI.
6. Validate `/api/health`, Firebase login, account isolation, one-use enrollment, signed daily claim/result sync, approvals and device revocation using real providers/devices.
7. Enable hourly retention with the dedicated scheduler OIDC identity. Budget alerts are notifications, not a hard invoice cap.

## Required preproduction gates

- PostgreSQL integration/concurrency tests for row locks, idempotency, nonce uniqueness, quotas and expired leases. Automated local cloud tests use SQLite and do not establish PostgreSQL locking behavior.
- Representative device bursts with staggered daily sync and a controlled dashboard-viewing load. Use `scripts/cloud_load.py` only on an authorized staging host with explicit cost approval; never commit its short-lived test-token file. The harness reports results for the requested load, not an automatically validated 100,000-user claim.
- Realistic dataset and retention tests, index/query plans, connection-pool pressure, database failover, backup restore, storage growth and p95/p99 latency measurements.
- Gateway/abuse rate limiting, WAF/DoS plan, dependency/container scanning, key rotation/revocation, privacy review and incident response. Application quotas do not substitute for internet-edge abuse controls.
- Native Windows installer, Credential Manager, scheduler sleep/logon behavior, local model performance and offline recovery.
- Provider-specific HubSpot/SAP/other connector authorization, response semantics and failure reconciliation. The universal protocol adapters are not certifications of every external system.
- Actual unit-cost measurements under the intended customer profile. Do not promise the $1 total cloud cost until measured.

## Product limitations remaining before an enterprise launch

Organization/team roles, enterprise SSO policies, PostgreSQL RLS, compliance certifications, payment/subscription billing, signed desktop installers, auto-update distribution, broad proprietary protocol adapters, validated database disaster recovery and sustained 100,000-account load evidence are not completed. They require a separate release gate; the UI and source do not claim otherwise.
