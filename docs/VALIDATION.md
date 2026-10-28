# Validation record

Validated in the managed Linux cloud environment on 28 October 2026. No successful model-generated implementation or native Windows execution is claimed.

| Check | Observed result |
| --- | --- |
| Locked Python installation and editable package | Passed |
| `python -m pytest -q` | **23 passed**, 0 failed, 0 skipped; one upstream Starlette/httpx deprecation warning |
| `npm ci` using writable workspace cache | Passed |
| `npm run build` | Passed, production React assets generated |
| `npm test` | **7 passed**, 0 failed, 0 skipped |
| Deterministic controller integration | Passed: temporary Git repositories, acceptance execution, independent fixture review, verified commits, ZIP/report generation and automatic next-task continuation |
| Actual subprocess adapter with fake Codex executable | Passed: read-only sandbox argv, stdin policy, schema/output parsing; this does not call a model |
| Failure/safety paths | Passed: dependency ordering, concurrent claims, crash recovery, dirty workspace preservation, bounded clean retries, STOP during active process, timeout, OS controller lock, estimate limit, Git-history tampering, sensitive staged files, delivery failure and unresolved dependencies |
| Private API | Passed: authentication, logout, origin/Host checks, workspace containment, acceptance validation, explicit usage approval, STOP and artifact traversal protection |
| Chromium dashboard smoke | Passed: local token login, all four navigation tabs, project dialog and 390px mobile layout without horizontal overflow; no page JavaScript errors |
| Read-only live Codex smoke | **Blocked**: injected Codex home is read-only; a writable runtime with references to existing authentication gets past initialization, then cloud proxy denies `chatgpt.com` with HTTP CONNECT 403. No model response completed. |
| Native Windows install and scheduler | **Not run**: this environment is Linux and has no Windows PowerShell |
| Docker / parallel isolation | **Not implemented**, optional future adapter |
| Provider billing enforcement | Estimated reservations only; provider-side spending caps remain operator-managed |

The saved cloud draft contains installation and startup instructions and the `chatgpt.com` custom domain addition. Saving a draft does not apply network policy or publish an environment. Review/save environment settings, publish, then retry a live read-only Codex smoke before claiming live autonomous readiness.

The dashboard is running locally with no fabricated projects, tasks or successful outcomes. Source archives exclude authentication bindings, uploaded `.env` files, local logs and controller state. The current source release is suitable for development and review; live Codex behavior and native Windows operation remain explicit validation limitations.

A subsequent Pages-preview change also passed seven frontend tests, both production build modes, and a static Chromium smoke with browser-only task persistence and zero controller API requests. See PREVIEW.md for publishing status and instructions.
