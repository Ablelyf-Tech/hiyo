# Hiyo product model

## Product

Hiyo is an industry-adaptive AI automation and intelligence platform for business departments. It coordinates existing systems and workflows. Engineering automation is one module, not the entire product.

Industry context → department goal → workflow → local/connected action → approval where required → signed outcome → account dashboard.

## Product surfaces

- **Command center**: actual workflows, completed local outcomes, approval queue and verified connector-request counts. No invented revenue, savings or active customer counts.
- **Workflows**: visual step editing, ordering, conditions, templates, execution and pause controls.
- **Industry library**: ten starting categories and fourteen templates, adaptable to other industries through the shared engine.
- **Intelligence**: department summaries grounded in recorded runs, plus local/provider-assisted workflow proposals for human review.
- **Connections**: one universal HTTPS connector with REST, GraphQL, SOAP and webhook protocols. Provider endpoints, permissions and schemas remain provider-specific.
- **Approvals**: human decisions before configured paid AI calls and external actions. Local AI does not itself incur a paid-provider approval; explicit approval steps remain supported.
- **Activity**: step outputs, failures, decisions and outcome provenance.
- **Account/device layer**: Firebase identity, enrolled computers, revocation, estimated usage, daily sync and bounded storage.

## Workload split

The cloud authenticates, stores account-scoped definitions and outcomes, leases jobs, records decisions and enforces usage quotas. Each enrolled computer executes the bounded local workflow engine and its configured connectors. Local models are the default for the cloud-sync tier. No arbitrary shell/code payload is accepted by this engine. The separately authorized engineering module can invoke sandboxed Codex in an authorized repository.

## Universal connector contract

A connected system must expose a supported accessible interface. REST, GraphQL, SOAP and webhooks are implemented. OAuth refresh, JDBC/ODBC, proprietary SDKs, UI-only applications, offline industrial protocols and unsupported vendor-specific actions require additional adapters. They are not represented as already implemented. HubSpot and SAP names indicate compatible API configuration targets, not validated partnerships or preauthorized access.

## Scale and unit economics

Design target: 100,000 enrolled accounts with staggered daily device sync, not 100,000 concurrent heavy AI jobs on the cloud. Target included platform cost: $1/account/month under explicit quotas. Neither capacity nor actual billed cost has been established in production. Enterprise team permissions, tenant-specific encryption keys, formal compliance certifications, disaster-recovery objectives and every connector's provider certification remain release gates or later work.

## Source provenance

The supplied Grofloo AI Business OS archive informed the broad business-automation framing. Blue Camel Decisions informed Decision → Action → Outcome → Proof. The supplied vehicle dashboard informed the calm modular composition. Hiyo is the product name. Imported `.env` files and document instructions were not imported as credentials or authority.
