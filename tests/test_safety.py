import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import pytest
from engineering_os.controller import Controller, Halt
from test_controller import FakeController, add_task


def test_stop_terminates_active_command(store, workspace):
    c = Controller(store)
    c.started = time.monotonic()
    result = []

    def work():
        try:
            c.command([sys.executable, "-c", "import time; time.sleep(30)"], workspace)
        except Halt:
            result.append("stopped")

    t = threading.Thread(target=work)
    t.start()
    time.sleep(0.2)
    (store.home / "STOP").touch()
    t.join(4)
    assert not t.is_alive() and result == ["stopped"]


def test_worker_blocker_never_checkpoints(store, workspace):
    add_task(store, workspace)

    class Blocked(FakeController):
        def worker(self, *args, **kwargs):
            raise Halt("Production deployment requires approval")

    assert Blocked(store).run() == "stopped"
    assert store.snapshot()["tasks"][0]["checkpoint"] is None


def test_sensitive_staged_files_block_commit(store, workspace):
    add_task(store, workspace)

    class UnsafeBuilder(FakeController):
        def worker(self, task, role, prompt, readonly=False):
            result = super().worker(task, role, prompt, readonly)
            if role == "Builder":
                (workspace / ".env").write_text("NOT_A_REAL_SECRET=fixture")
            return result

    assert UnsafeBuilder(store).run() == "stopped"
    task = store.snapshot()["tasks"][0]
    assert task["checkpoint"] is None
    assert "Sensitive configuration" in task["error"]


def test_git_history_change_is_blocked(store, workspace):
    add_task(store, workspace)

    class BadWorker(FakeController):
        def worker(self, task, role, prompt, readonly=False):
            result = super().worker(task, role, prompt, readonly)
            if role == "Builder":
                subprocess.run(["git", "add", "."], cwd=workspace, check=True)
                subprocess.run(
                    ["git", "commit", "-m", "unauthorized worker commit"],
                    cwd=workspace,
                    check=True,
                    capture_output=True,
                )
            return result

    assert BadWorker(store).run() == "stopped"
    assert "changed Git history" in store.snapshot()["tasks"][0]["error"]


def test_unresolved_dependencies_do_not_complete_run(store, workspace):
    tid = add_task(store, workspace)
    pid = store.snapshot()["projects"][0]["id"]
    store.update(tid, status="blocked", error="Required external approval")
    store.task(
        pid,
        "Dependent",
        "Implement next required outcome",
        [[sys.executable, "-V"]],
        [tid],
    )
    assert FakeController(store).run() == "blocked"
    assert store.snapshot()["tasks"][1]["status"] == "queued"


def test_delivery_failure_does_not_automatically_reexecute_task(store, workspace):
    add_task(store, workspace)

    class DeliveryFailure(FakeController):
        def git(self, ws, *args):
            if args[0] == "archive":
                raise RuntimeError("Fixture archive failure")
            return super().git(ws, *args)

    assert DeliveryFailure(store).run() == "stopped"
    task = store.snapshot()["tasks"][0]
    assert task["attempts"] == 1 and task["status"] == "blocked"
    assert task["checkpoint"]
