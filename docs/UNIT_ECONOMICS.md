# $1/account/month platform cost target

The target is **total platform cloud operating cost per account**, not an invented current invoice. No GCP resources have been deployed, so actual spend and capacity have not been measured.

## Included default execution profile

- Business inference and workflow computation run on enrolled user computers.
- No paid cloud model is invoked by the cloud-sync device tier.
- At most 1,000 queued jobs/account/month, 64 MiB combined upload/dashboard response budget and 10,000 authenticated requests/month.
- At most 100 definitions/account, 16 KiB per definition, 128 KiB per job, 64 KiB per result, 20 steps per workflow and three active devices.
- Thirty-day cloud job/result retention and small, on-demand evidence downloads.
- Cloud dashboard polling is once per minute while visible, rather than every few seconds in background tabs.

Application reservations are $0.25 base + $0.0005/job. The maximum 1,000-job reservation is $0.75/account/month, leaving a nominal $0.25 margin to the $1 target. **These are planning allocations, not measured GCP unit prices.** Quotas stop additional application usage when limits are reached. They cannot make shared infrastructure, attack traffic, logging, backups, identity-provider pricing or every possible network charge fit a guaranteed invoice.

At 100,000 accounts, a $1 allocation implies a $100,000/month aggregate ceiling. Real cost must be modeled from actual active accounts, jobs, database/storage utilization, auth MAUs, egress and regional prices. Shared regional PostgreSQL has a fixed baseline, so $1/account may be infeasible at very small pilot volumes. Terraform's pilot budget defaults to $100 in **alerts**, not to $100,000 and not to a hard shutoff.

## Launch cost gates

1. Obtain current official regional prices and the identity provider's relevant MAU plan.
2. Run an approved staging workload using representative account activity and bytes, including idle users.
3. Measure Cloud Run requests/CPU, SQL CPU/IOPS/storage, backups, Secret Manager, auth, scheduler and egress.
4. Allocate shared cost per active account and include support/operations reserves as required by the business.
5. Verify p95 cost and heavy-use distributions remain below the target, or reduce quotas/adjust the product before promising it.
6. Configure budget alerts, anomaly monitoring, abuse protection and a reviewed operational shutdown procedure. GCP budgets alone do not enforce a billing cap.

Device purchase, electricity, internet access, third-party SaaS subscriptions and optional external service/API charges remain outside platform hosting allocations. A promise of “everything in the world for $1” is not technically or financially established by this code. Production pricing, payment collection and tax/subscription billing are not implemented.
