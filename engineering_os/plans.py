"""Human-reviewed plan ingestion. The model cannot approve its own task backlog."""

from pathlib import Path
from .store import Store


def import_plan(store: Store, plan: dict, workspace: Path):
    from pydantic import BaseModel, Field

    class Task(BaseModel):
        key: str = Field(min_length=1)
        title: str = Field(min_length=1)
        spec: str = Field(min_length=10)
        checks: list[list[str]] = Field(min_length=1)
        dependencies: list[str] = []
        priority: int = 0

    class Plan(BaseModel):
        name: str = Field(min_length=1)
        brief: str = Field(min_length=10)
        tasks: list[Task] = Field(min_length=1)

    parsed = Plan.model_validate(plan)
    keys = set()
    for task in parsed.tasks:
        if task.key in keys or any(d not in keys for d in task.dependencies):
            raise ValueError("Tasks need unique keys and earlier dependencies")
        if any(
            not c or any(not isinstance(a, str) or not a for a in c)
            for c in task.checks
        ):
            raise ValueError("Nonempty argv acceptance commands required")
        keys.add(task.key)
    workspace = workspace.resolve()
    if not workspace.is_dir() or not (workspace / ".git").exists():
        raise ValueError("Existing Git workspace required")
    if (
        store.home == workspace
        or store.home.is_relative_to(workspace)
        or workspace.is_relative_to(store.home)
    ):
        raise ValueError("State must be outside project workspace")
    pid = store.project(parsed.name, parsed.brief, workspace)
    ids = {}
    for task in parsed.tasks:
        ids[task.key] = store.task(
            pid,
            task.title,
            task.spec,
            task.checks,
            [ids[d] for d in task.dependencies],
            task.priority,
        )
    return pid
