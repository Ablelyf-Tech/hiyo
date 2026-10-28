# Architecture

```
React dashboard → loopback FastAPI → SQLite queue + JSON event mirror
                                  → single controller lock
                                  → sandboxed Codex CLI workers
                                  → independent local acceptance runner
                                  → read-only reviewer
                                  → Git checkpoint + artifact directory
```

`engineering_os/store.py` owns WAL-mode SQLite transactions. Atomic claims use `BEGIN IMMEDIATE`; dependencies must be previously defined tasks in the same project. `controller.py` owns process groups, time/output/call/estimate limits and the lifecycle. Workers cannot choose their own completion status. Read-only roles run with Codex's read-only sandbox; Builder and Debugger use workspace-write, no sandbox network and no automatic approvals. A CLI or sandbox failure is a task failure, never an unsandboxed fallback.

`api.py` exposes authenticated project/task/control/state/artifact endpoints. It generates a local token, exchanges it for an HttpOnly SameSite=Strict cookie, checks origins and Host headers, disables API docs and binds to loopback through the CLI. React polls every two seconds; this is near-live status, not a WebSocket stream. Evidence includes command exit codes, worker reports, failures and Git branch/checkpoint events.

Controller state is outside managed workspaces: `state.sqlite3`, `events.jsonl`, `dashboard-token`, `controller.lock`, `logs/`, `artifacts/<task-id>/`, and optional `STOP`. Never commit this directory. Prepared dependencies and built dashboard files persist on disk; running processes do not survive environment snapshots.

No external database or Supabase credentials are needed. Schema initialization is idempotent. Schema version migrations will be required before changing persisted tables in a later release. Multiple dashboards may read the same state; only one controller may execute it. Parallel editing of the same repository by another process is unsupported.
