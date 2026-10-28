"""Generate a proposed backlog; executing it requires a separate reviewed import."""

import json
import time
from pathlib import Path
from .controller import Controller, POLICY
from .store import Store


def propose(store: Store, workspace: Path, brief: str, output: Path):
    workspace = workspace.resolve()
    output = output.resolve()
    if not workspace.is_dir() or not (workspace / ".git").exists():
        raise ValueError("An existing Git workspace is required")
    if output.is_relative_to(workspace) or store.home.is_relative_to(workspace):
        raise ValueError("Proposal and controller state must be outside the workspace")
    if output.exists():
        raise ValueError("Refusing to overwrite an existing proposal")
    item = {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
            "title": {"type": "string"},
            "spec": {"type": "string"},
            "checks": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            },
            "dependencies": {"type": "array", "items": {"type": "string"}},
            "priority": {"type": "integer"},
        },
        "required": ["key", "title", "spec", "checks", "dependencies", "priority"],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "brief": {"type": "string"},
            "tasks": {"type": "array", "minItems": 1, "items": item},
        },
        "required": ["name", "brief", "tasks"],
        "additionalProperties": False,
    }
    schema_path = store.home / "plan-schema.json"
    schema_path.write_text(json.dumps(schema))
    c = Controller(store)
    c.started = time.monotonic()
    output.parent.mkdir(parents=True, exist_ok=True)
    code, _, _ = c.command(
        [
            "codex",
            "exec",
            "--sandbox",
            "read-only",
            "--json",
            "-c",
            'approval_policy="never"',
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output),
            "-C",
            str(workspace),
            "-",
        ],
        workspace,
        role="Planner",
        stdin=POLICY
        + "\nInspect the repository and propose an ordered executable backlog. "
        "Every task must include concrete acceptance criteria and noninteractive test/build argv commands. "
        "Dependencies refer only to earlier task keys. Include delivery documentation. Never use destructive, "
        "deployment or external communication commands. Product brief:\n" + brief,
    )
    if code or not output.is_file():
        raise RuntimeError("Planner failed; inspect local controller logs")
    result = json.loads(output.read_text(encoding="utf-8"))
    if not result.get("tasks"):
        raise RuntimeError("Planner returned an empty backlog")
    return output
