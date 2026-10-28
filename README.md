# Hiyo Engineering OS

A private, Windows-first engineering command center powered by **Codex CLI**, Python, SQLite, FastAPI and React. It combines the Grofloo source’s business automation framing with Blue Camel's **Decision → Action → Outcome → Proof** model. The supplied vehicle dashboard informs its quiet three-column composition, route map, control tiles and execution instrument panel.

This is an executable local controller, not a hosted SaaS. Connect trusted Git repositories, approve a task backlog and acceptance commands, then let the controller continue until it finishes or encounters a blocker or limit. No model-generated test result can substitute for an actual command exit and an independent review.

## Windows installation

Prerequisites: Windows 10/11, Python 3.11+, Git, Node.js 22+, a current OpenAI Codex CLI supporting `exec --sandbox --output-schema`, and an authorized Codex account. Install prerequisites using their official installers. Then, from a normal PowerShell window:

```powershell
git clone https://github.com/Ablelyf-Tech/hiyo.git
cd hiyo
.\scripts\install.ps1
npm install -g @openai/codex
codex login
.\scripts\start.ps1 -ProjectsRoot C:\Projects
```

The dashboard binds **only to 127.0.0.1:8787**. Read `%LOCALAPPDATA%\Hiyo\dashboard-token` locally and paste it into the login form. This is a local authentication token; never publish it. Create an existing Git repository under `C:\Projects`, configure your Git author, make an initial commit, and connect it from the dashboard. Keep this controller checkout and its state outside managed project workspaces.

Native Windows Codex sandbox support depends on the installed Codex version and Windows setup. If the CLI cannot establish its sandbox, execution fails; never use bypass flags. WSL2 is an alternative, with the controller, Git, Python and Codex all installed inside the same Linux environment. Native Windows installation and Task Scheduler execution still require validation on Windows; development validation here ran on Linux.

## Linux / cloud development

```bash
./scripts/setup.sh
.venv/bin/python -m engineering_os.cli --home /workspace/hiyo-state serve \
  --projects-root /workspace/projects --dashboard dashboard/dist
```

The setup script uses `/workspace/.npm-cache` in the cloud; elsewhere set an appropriate npm cache or run `npm ci` directly. Development hot reload: run `npm run dev` in `dashboard/` alongside the API; Vite proxies `/api` to the local API. No external fonts or services are required for the dashboard.

## Run an approved backlog

Use the dashboard to create tasks, or review `examples/plan.json` and import a plan:

```powershell
.\.venv\Scripts\python.exe -m engineering_os.cli --home "$env:LOCALAPPDATA\Hiyo" import-plan examples\plan.json --workspace C:\Projects\notes
.\.venv\Scripts\python.exe -m engineering_os.cli --home "$env:LOCALAPPDATA\Hiyo" run --approve-codex-usage --max-seconds 3600 --max-calls 20 --estimated-budget 5
```

For a generated backlog, write a product brief to a text file and run `propose-plan --workspace <repo> --brief <file> --output <outside-repo.json> --approve-codex-usage`. This uses a read-only Codex Planner. **Review all proposed commands before `import-plan`**; generation does not authorize execution. Dependencies must reference earlier task keys, so cycles cannot enter an imported plan.

Every task must have nonempty noninteractive acceptance commands represented as argv arrays, e.g. `[["python", "-m", "pytest", "-q"], ["npm.cmd", "run", "build"]]`. On native Windows use `npm.cmd` and `npx.cmd`; avoid PowerShell wrappers when direct executables work. Test dependencies must already be installed in the environment used by the controller. Run from the intended activated environment. Starting the dashboard does not automatically start model work.

## Execution lifecycle

1. SQLite atomically claims the highest-priority eligible task after its dependencies complete.
2. Read-only **Planner** and **Architect** inspect requirements and the repository.
3. **Builder** runs Codex with `workspace-write`, approval policy `never`, and sandbox network access disabled. It must stop when an operation requires approval.
4. **Tester** executes the human-approved argv commands independently, captures exit codes and bounded output, and records evidence.
5. If checks fail, **Debugger** attempts repairs and the controller reruns the acceptance checks.
6. A separate read-only **Reviewer** inspects the final diff. Only a passed review and passed commands permit a checkpoint.
7. **Delivery Manager** creates a Git commit, source ZIP, test report and release note. The next eligible task starts automatically.

The default mode is sequential with an OS-level single-controller lock. Each task gets a unique Git branch. Branches build on the currently checked-out verified history; the controller does not merge or push. Optional parallel execution and Docker-based isolation are **not implemented**. Use separate controller instances with separate state directories and nonoverlapping repositories if running independent projects; never share a working tree.

## Limits and stopping

Default run limits: 1 hour, 600 seconds per command, 20 Codex calls, 3 task attempts, and a $5 **estimated** budget with $0.25 reserved per Codex call. Clean transient failures use exponential backoff. Dirty failures block immediately and preserve the working diff. These reservations are estimates, **not actual billing or a hard provider spending cap**. Set an account spending cap with the provider. No unknown token price or claimed free execution is assumed.

Click emergency stop, create a `STOP` file in the state directory, or run `hiyo --home <state> stop`. Active process groups are terminated (Windows uses `taskkill /T /F`). SIGINT/SIGTERM also request shutdown for CLI workers. Inspect the workspace after a stop. Clearing STOP never starts work by itself. An interrupted running task is marked blocked at the next controller launch; inspect and commit your intended changes or repair the workspace, then explicitly retry. Logs, attempts, dependencies, verified commits, and budget reservations persist in SQLite. Budgets apply per authorized run.

## Tests and evidence

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd dashboard
npm.cmd test
npm.cmd run build
```

Backend tests use temporary Git repositories and a deterministic model replacement. One adapter test invokes a fake executable to verify CLI arguments, sandbox selection, stdin and report parsing. These are **not live model integration tests**. See `docs/VALIDATION.md` for the observed validation and its limits.

## Windows restart support

```powershell
.\scripts\register-scheduler.ps1 -ProjectsRoot C:\Projects
```

Registers a least-privilege, current-user logon task with three one-minute restart attempts. It restarts the private dashboard, not a paid run or an interrupted task. Do not enable elevated privileges or disable PowerShell execution policy. If your organization's policy blocks scripts, request its normal signed-script process. Task registration is an explicit local action; no task is registered during installation.

See [product model](docs/PRODUCT.md), [architecture](docs/ARCHITECTURE.md), [security boundaries](docs/SECURITY.md), and [operations](docs/OPERATIONS.md).

## Source release packaging

After building, run `python scripts/package_release.py <outside-checkout.zip>`. The ZIP includes tracked source and built dashboard assets, with a SHA-256 sidecar. It excludes local state, tokens, virtual environments and package caches.

In managed cloud environments where the injected Codex home is read-only, `HIYO_CODEX_HOME` can point to a writable Codex runtime directory. The controller uses it only for Codex child processes; authentication should remain an existing injected binding. Do not copy credentials into source or logs. This override is unnecessary for a normal writable Windows user profile.

## Public dashboard preview

A browser-only preview is prepared on the `gh-pages` branch. It includes clearly labeled sample tasks and saves edits in your browser; it never connects to the private controller or runs Codex. See [Pages setup and preview limits](docs/PREVIEW.md). The expected address is `https://ablelyf-tech.github.io/hiyo/` after Pages is enabled for the branch in repository settings.

### Existing installations

The product is named Hiyo. New installations use the `hiyo` command and Hiyo state paths. If upgrading an earlier development snapshot, keep using `--home <existing-state-directory>` (or PowerShell `-StateDirectory`) to preserve your queue and token; do not delete or move existing state blindly. The old `GROFLOO_CODEX_HOME` override remains accepted as a compatibility fallback, while new setups use `HIYO_CODEX_HOME`. Existing Windows scheduled tasks are not renamed automatically; remove the old task deliberately before registering Hiyo.
