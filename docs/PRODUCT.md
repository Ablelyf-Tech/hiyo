# Product model — Grofloo Engineering OS

## Positioning

An accountable engineering autopilot for founders and small teams: convert business goals into working software while retaining explicit control of risk and proof. The first release is a private, single-user local application. It is not the entire CRM, HR, finance, or ERP suite advertised in the Grofloo landing page.

## Source synthesis

- **Grofloo AI Business OS**: unified workspace, business automation intent, AI copilot and operational overview. The archive is primarily a TanStack marketing site. Its broad business-module promises are context, not implemented integrations.
- **Blue Camel Decisions**: decision intelligence, executive summary, decisions/actions/outcomes, approval context and proof. The archive is a Vite/React/Supabase application. Its `.env` and existing backend bindings were excluded; this product uses its own local SQLite data model.
- **Provided vehicle dashboard**: three-column composition, a route on the left, worker controls in the middle, and an execution instrument on the right. No Tesla branding, imagery or vehicle functionality is included.

The two apps have incompatible routing/backend assumptions. Rather than nest disconnected UIs or copy live credentials, this repository implements a unified Python/React product around their shared intent. No imported document instruction or AGENTS.md was promoted to user authority. Existing archive app modules remain in the supplied originals, not falsely presented as integrated services.

## Domain model

Business brief → Project → approved Task → dependency-ready queue → engineering workers → command evidence → independent review → verified Git checkpoint → delivery artifacts.

A project owns a trusted Git workspace. Tasks contain a title, specification, priority, immutable-to-workers acceptance argv, dependencies, attempt count and stage. Events provide ordered evidence. Runs capture timing, status and estimated cost reservations. SQLite, JSON logs, reports, release notes and source archives provide traceability.

## Core journeys

1. Connect a Git workspace, enter the business goal and create a task with observable acceptance criteria.
2. Optionally generate a read-only model backlog and import it after human command review.
3. Approve model use and limits once for the backlog. Eligible tasks continue without a prompt after each task.
4. Read evidence when something fails; stop, inspect and explicitly retry uncertain changes.
5. Download delivery artifacts and perform deployment only through a separately approved process.

## Completion definition

A task completes only after all its stored acceptance commands exit zero, a separate read-only review returns passed, a verified Git checkpoint exists, and release evidence is generated. Meaningful acceptance commands are the plan approver's responsibility; `echo success` proves nothing. Pytest's zero-test exit (5) fails normally. Semantic acceptance still requires sufficient tests and review; a model review is not a formal proof.

A project is delivery-ready when every required approved task is complete and its backlog includes successful tests, required builds, operating documentation and delivery checks. The controller makes no global completeness claim about unrepresented requirements. It does not treat an empty backlog as a completed product.

## Release scope

Included: sequential autonomous orchestration, plan generation/import, seven engineering roles (Tester and Delivery Manager are deterministic controller stages), SQLite recovery, backoff, limits, STOP, Git branches/commits, private dashboard, downloads, Windows setup and scheduler scripts.

Future work: isolated parallel workers, Docker execution adapter, enterprise identity, role-based approval integration, provider-enforced spend accounting, remote multi-user hosting, and real CRM/ERP connectors. None are represented as functioning features in this release.
