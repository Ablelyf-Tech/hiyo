import json
import subprocess
import sys
import time
from pathlib import Path
import pytest
from engineering_os.controller import Controller, Limits, Halt


class FakeController(Controller):
    """Deterministic model replacement, not a live Codex test."""

    def worker(self, task, role, prompt, readonly=False):
        self.store.update(task["id"], stage=role)
        self.store.event(
            task["id"], role, "report", status="passed", summary="Fixture report"
        )
        if role == "Builder":
            (Path(task["workspace"]) / "feature.txt").write_text("working feature")
        return {"status": "passed", "summary": "Fixture report"}


def add_task(store, workspace, checks=None):
    pid = store.project("Sample", "Build a sample feature", workspace)
    return store.task(
        pid,
        "Feature",
        "Implement feature.txt containing working feature",
        checks
        or [
            [
                sys.executable,
                "-c",
                "from pathlib import Path; assert Path('feature.txt').read_text() == 'working feature'",
            ]
        ],
    )


def test_verified_commit_and_artifact_with_continuation(store, workspace):
    tid = add_task(store, workspace)
    pid = store.snapshot()["projects"][0]["id"]
    second = store.task(
        pid,
        "Next",
        "Verify the previous feature",
        [
            [
                sys.executable,
                "-c",
                "from pathlib import Path; assert Path('feature.txt').exists()",
            ]
        ],
        [tid],
    )
    controller = FakeController(store)
    assert controller.run() == "completed"
    tasks = store.snapshot()["tasks"]
    assert [t["status"] for t in tasks] == ["completed", "completed"]
    assert all(t["checkpoint"] for t in tasks)
    assert (store.home / "artifacts" / tid / "source.zip").is_file()
    report = json.loads(
        (store.home / "artifacts" / tid / "test-report.json").read_text()
    )
    assert report[0]["exit_code"] == 0
    assert (
        subprocess.check_output(["git", "status", "--porcelain"], cwd=workspace) == b""
    )


def test_failed_acceptance_never_completes_and_keeps_diff(store, workspace):
    tid = add_task(store, workspace, [[sys.executable, "-c", "raise SystemExit(1)"]])
    assert FakeController(store).run() == "stopped"
    task = store.snapshot()["tasks"][0]
    assert task["status"] == "blocked" and task["checkpoint"] is None
    assert "Acceptance checks failed" in task["error"]
    assert (workspace / "feature.txt").exists()
    assert not (store.home / "artifacts" / tid).exists()


def test_dirty_workspace_not_modified(store, workspace):
    add_task(store, workspace)
    (workspace / "user.txt").write_text("preserve me")
    assert FakeController(store).run() == "stopped"
    assert (workspace / "user.txt").read_text() == "preserve me"
    assert "uncommitted" in store.snapshot()["tasks"][0]["error"]


def test_stop_timeout_and_single_controller(store, workspace):
    controller = Controller(store, Limits(call_seconds=1))
    controller.started = time.monotonic()
    with pytest.raises(TimeoutError):
        controller.command(
            [sys.executable, "-c", "import time; time.sleep(20)"], workspace
        )
    (store.home / "STOP").touch()
    with pytest.raises(Halt):
        controller.command([sys.executable, "-V"], workspace)
    controller.acquire()
    try:
        with pytest.raises(Halt):
            Controller(store).acquire()
    finally:
        controller.lock.close()


def test_budget_and_call_limits_before_model_execution(store, workspace):
    controller = Controller(store, Limits(estimated_budget=0.1, reserve_per_call=0.25))
    controller.started = time.monotonic()
    with pytest.raises(Halt, match="budget"):
        controller.worker(
            {"id": "x", "workspace": str(workspace)}, "Planner", "Test", True
        )
    assert controller.calls == 0


def test_real_cli_adapter_contract_with_fake_executable(store, workspace, tmp_path):
    # Tests actual subprocess argv, stdin, schema/output parsing, and sandbox selection.
    fake = tmp_path / "fake-codex.py"
    fake.write_text("""import sys,json,pathlib
args=sys.argv[1:]
assert args[0]=='exec' and args[args.index('--sandbox')+1]=='read-only'
assert 'Never deploy' in sys.stdin.read()
p=pathlib.Path(args[args.index('--output-last-message')+1])
p.write_text(json.dumps({'status':'passed','summary':'fixture only'}))
print(json.dumps({'type':'fixture'}))
""")
    controller = Controller(store)
    controller.started = time.monotonic()
    original = controller.command
    controller.command = lambda argv, *a, **kw: original(
        [sys.executable, str(fake), *argv[1:]], *a, **kw
    )
    result = controller.worker(
        {"id": "fixture", "workspace": str(workspace)}, "Reviewer", "Inspect diff", True
    )
    assert result["summary"] == "fixture only"
    assert controller.calls == 1


def test_clean_transient_failure_retries_with_bound(store, workspace):
    add_task(store, workspace)

    class Failing(Controller):
        def worker(self, *args, **kwargs):
            raise RuntimeError("Transient fixture failure")

    c = Failing(store, Limits(max_attempts=2, backoff_seconds=0.01))
    assert c.run() == "stopped"
    task = store.snapshot()["tasks"][0]
    assert task["attempts"] == 2 and task["status"] == "blocked"
    failures = [e for e in store.snapshot()["events"] if e["kind"] == "failure"]
    assert {e["data"]["retry"] for e in failures} == {True, False}
