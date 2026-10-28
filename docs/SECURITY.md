# Security boundaries

This is a local trusted-operator development tool. Do not expose its port publicly. It has no multi-user authorization, TLS termination, network rate limiting, enterprise audit guarantees or hostile-tenant isolation. The local token grants full controller authority. The server never includes token contents in API state.

Codex sandboxing is mandatory. No dangerous bypass flag is used. Approval requests are denied noninteractively; production deployments, purchases, credential changes, destructive operations and external communications must be handled separately after explicit human approval. The controller never automatically pushes or deploys. Builder/Debugger network access is disabled in the configured Codex sandbox. The host's platform egress policy still applies.

**Acceptance commands run on the host with the controller user's permissions.** They are explicitly approved, trusted test/build commands. Tests and dependency scripts execute code; Codex's command sandbox does not isolate this independent runner. Do not use this release on malicious repositories, untrusted package install scripts or hostile generated tests with access to valuable host data. Use an isolated development VM and least-privilege account. Optional container/parallel isolation is not implemented. Prompts and read-only model review are defense in depth, not a hard boundary against hostile code.

SQLite metadata and acceptance commands live outside project workspaces. The task runner rejects dirty workspaces before starting, never discards a failed working diff, and stops if a worker changes Git HEAD. Filename checks block common `.env`, PEM/key/PFX files from automatic commits, but this is not a complete secret scanner. Review staged files and configure an organizational secret scanner before pushing any repository. Artifacts contain tracked source; never track credentials.

No archive `.env` was imported. Raw command/model logs are retained locally and may contain sensitive application output. Restrict state directory permissions (on Windows use the current user's profile ACL), do not upload logs blindly, and do not publish controller state or tokens. Unix token creation uses mode 0600. Windows relies on inherited user-profile ACLs.

STOP terminates the observed process tree, but it is not an OS emergency boundary against deliberately escaping or detached processes. Native Windows process termination and sandbox behavior require Windows validation. Always inspect a stopped or crashed workspace before approving continuation. Checkpoint commits and failed branches are preserved; retrying does not reset history.

Estimated cost reservations do not bound provider billing. Use provider-side spending controls. Codex authentication is supplied separately by the operator; never paste API secrets into task specifications, saved plans, Git commits or the dashboard token field.
