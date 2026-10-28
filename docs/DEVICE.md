# Daily device execution and dashboard sync

## Enrollment and identity

After deployment, a Firebase-authenticated account downloads a one-time enrollment ticket from its dashboard. It expires in 15 minutes and allows one registration. No long-lived Firebase refresh token is copied to the device. The agent generates an Ed25519 key pair, stores the private key in the native OS credential store through keyring and uploads the public key. It refuses a plaintext key fallback. Device configuration contains only the cloud URL, device ID and an OS-key-store reference.

`install-device.ps1` enrolls the current user and explicitly registers a least-privilege interactive Windows scheduled task. Default: 09:00 in that computer's local timezone, up to one hour of randomized delay. StartWhenAvailable handles missed starts when Windows permits it. The user must be logged in; the task cannot compute while a computer is powered off, asleep indefinitely or unavailable. No hidden background installation is performed.

## Daily processing

1. Publish connector capability metadata (never secrets).
2. Sign a POST claim with method/path/body digest, timestamp and random nonce.
3. Claim only an eligible job belonging to the enrolled account. A job needing a particular connector is routed to a device advertising that connector.
4. Validate its typed workflow and run local transformations, conditions, local AI and approved connector requests. The job cannot supply arbitrary shell/Python code.
5. Keep full local state/evidence in SQLite and upload a bounded signed result.
6. The cloud verifies account/device/lease, required approval evidence, cursor and outcome fields; the dashboard shows the recorded state.

The agent handles at most 32 jobs or 30 minutes per daily run, with 20 steps per workflow and bounded request durations. It uses an already-installed local Ollama model (default `llama3.2:3b`), never a paid cloud inference fallback. Hardware performance and electricity are the device owner's responsibility. No model is silently downloaded.

A workflow waiting for approval remains pending until the account owner approves through the dashboard. Continuation occurs on the next device sync; run `hiyo-agent --home <device-state> daily` manually for an earlier sync. This is not a promised instantaneous 24/7 execution service.

## Stop and recovery

Use `hiyo-agent --home <state> stop` or create `STOP` in the device state directory. It prevents subsequent claims; the local engine checks its stop state between steps. In-flight external requests cannot be recalled. `clear-stop` clears the explicit local stop and does not start work itself.

A cloud result submission failure preserves local completion, and a future valid claim can upload it without rerunning completed steps. Interrupted/blocked runs require an explicit inspected resume; a crash around an external request can leave its outcome uncertain. Do not treat a failed network response as proof the provider did nothing. Revoke lost devices from the account API/dashboard before re-enrolling them.

Native Windows Task Scheduler, Windows Credential Manager, a real Ollama model and a real GCP/Firebase deployment have not been exercised in this Linux environment. Automated device tests use a memory key-store fixture and real Ed25519 signatures against an in-process cloud API. They establish protocol behavior, not native Windows installation readiness.
