# Operations and delivery

## Prepare a project

Use a trusted, existing Git repository with an initial commit and a clean working tree. Configure Git name/email yourself. Initialize empty projects explicitly with `git init`, add an initial README, then commit it. Put the controller checkout and its state outside the managed repository. Dependencies must be installed before enabling autonomous work; paid dependency provisioning or credential setup requires separate approval.

Import a reviewed plan or add tasks through the dashboard. Include all functional tests, required builds, migrations, packaging and documentation checks in the approved backlog. Use direct argv lists; shell operators are not expanded. Noninteractive checks must finish within the per-command limit. A skipped test does not prove a behavior; reviewers and plan authors must inspect coverage.

## Blockers and restart

A clean transient failure retries with 10s, 20s, 40s backoff up to the attempt limit. A dirty failure stops immediately. Logs record the exact failure; no changes are discarded. Read the evidence and `git status`, inspect diffs, make an intentional checkpoint or repair, and retry the blocked task. Review earlier attempts' branches before switching them. Controller crash recovery blocks in-flight work because whether the last operation finished may be uncertain. Never delete a live controller lock; advisory locks release automatically when the process exits.

STOP is persistent across restarts and publication. Clear it only after inspection. The Windows scheduled task restarts the dashboard at user logon/on failure but does not approve Codex usage, auto-clear STOP or blindly restart interrupted tasks. Start the approved queue from the dashboard after inspecting recovery status. CLI run SIGINT/SIGTERM requests a controlled stop; forced process termination may leave a dirty workspace.

## Backups

Stop the controller and dashboard before copying the state directory and Git repositories. SQLite WAL files are part of a live database; use SQLite's backup API if backing up while running. Protect token and logs as sensitive data. Restore the same workspace paths or re-register projects deliberately; do not rewrite SQLite blindly. Rotation of the dashboard token is a separate human credential change: stop server, securely remove token file, restart and use the new local token. Existing sessions are invalidated on server restart.

## Artifacts and release

Each verified task receives `source.zip` (Git-tracked files at the verified commit), `test-report.json` (actual acceptance command exits and bounded output) and `release.md` (commit and verification summary). Events/logs retain independent reviewer evidence. A source ZIP excludes untracked ignored dependencies; install using the project's own documented dependencies. No source archive is a deployed service. Check repository README deployment instructions and approve the target deployment separately.

For this product: build the React dashboard with `npm ci && npm run build`, install the Python package, then start the FastAPI server with `--dashboard <dist path>`. Keep loopback binding. The installer references the source checkout's built dashboard; a standalone Python wheel does not bundle React assets. Distributing a portable Windows executable/installer is outside this source release; use the supplied PowerShell installer on a machine with prerequisites.

## Optional isolation

Use a disposable VM for each independently trusted project. Docker-based execution and automatic parallel work are future adapters; do not present manually launched containers as enforced isolation in this release. Current instances must use disjoint state directories and working trees. Do not create worktrees during cloud environment onboarding; each cloud task is already isolated.
