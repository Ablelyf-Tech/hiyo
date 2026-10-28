from __future__ import annotations
import hmac
import os
import secrets
import threading
from contextlib import asynccontextmanager
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .controller import Controller, Limits
from .store import Store
from .automation import Automation, automation_router


class Login(BaseModel):
    token: str


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    brief: str = Field(min_length=10, max_length=30000)
    workspace: str


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    spec: str = Field(min_length=10, max_length=30000)
    checks: list[list[str]]
    dependencies: list[str] = []
    priority: int = Field(default=0, ge=0, le=100)


class StartInput(BaseModel):
    approve_codex_usage: bool = False
    max_seconds: int = Field(default=3600, ge=10, le=86400)
    call_seconds: int = Field(default=600, ge=1, le=3600)
    max_attempts: int = Field(default=3, ge=1, le=10)
    max_calls: int = Field(default=20, ge=1, le=500)
    estimated_budget: float = Field(default=5, gt=0, le=1000)
    reserve_per_call: float = Field(default=0.25, gt=0, le=100)


def create_app(home: Path, projects_root: Path, dashboard: Path | None = None):
    store = Store(home)
    automation = Automation(store)
    root = projects_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    token_path = store.home / "dashboard-token"
    if not token_path.exists():
        fd = os.open(token_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(32))
    token = token_path.read_text().strip()
    if len(token) < 32:
        raise RuntimeError(
            "Invalid local dashboard token file; inspect it before restarting"
        )
    session_token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        scheduler = threading.Thread(target=automation.loop, daemon=True)
        scheduler.start()
        yield
        automation.shutdown.set()
        await asyncio.to_thread(scheduler.join, 5)
        if app.state.controller:
            app.state.controller.stop.set()
        if app.state.thread and app.state.thread.is_alive():
            (store.home / "STOP").touch()
            await asyncio.to_thread(app.state.thread.join, 5)

    app = FastAPI(
        title="Hiyo AI Automation OS",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"],
    )
    app.state.store = store
    app.state.controller = None
    app.state.thread = None
    mutex = threading.Lock()

    @app.middleware("http")
    async def private_api(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if (
                origin
                and origin != f'{request.url.scheme}://{request.headers.get("host")}'
            ):
                return Response("Cross-origin requests forbidden", status_code=403)
            if request.url.path not in ("/api/login", "/api/health"):
                supplied = request.headers.get("x-dashboard-token", "")
                cookie = request.cookies.get("hiyo_session", "")
                if not (
                    hmac.compare_digest(supplied.encode(), token.encode())
                    or hmac.compare_digest(cookie.encode(), session_token.encode())
                ):
                    return Response("Authentication required", status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
        )
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/login")
    def login(body: Login, response: Response):
        if not hmac.compare_digest(body.token.encode(), token.encode()):
            raise HTTPException(401, "Invalid token")
        response.set_cookie(
            "hiyo_session",
            session_token,
            httponly=True,
            samesite="strict",
            max_age=28800,
        )
        return {"authenticated": True}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie("hiyo_session")
        return {"authenticated": False}

    @app.get("/api/state")
    def state():
        data = store.snapshot()
        data["running"] = bool(app.state.thread and app.state.thread.is_alive())
        data["stopped"] = (store.home / "STOP").exists()
        data["projects_root"] = str(root)
        data["artifacts"] = [
            str(p.relative_to(store.home / "artifacts")).replace("\\", "/")
            for p in (store.home / "artifacts").rglob("*")
            if p.is_file()
        ]
        return data

    @app.post("/api/projects")
    def project(body: ProjectInput):
        path = (root / body.workspace).resolve()
        if path == root or not path.is_relative_to(root) or not path.is_dir():
            raise HTTPException(
                400,
                "Select an existing Git workspace below the configured projects root",
            )
        if (
            path == store.home
            or store.home.is_relative_to(path)
            or path.is_relative_to(store.home)
        ):
            raise HTTPException(
                400, "Controller state and project workspaces must be separate"
            )
        try:
            return {"id": store.project(body.name, body.brief, path)}
        except Exception as exc:
            raise HTTPException(400, "Workspace already registered or invalid") from exc

    @app.post("/api/projects/{pid}/tasks")
    def task(pid: str, body: TaskInput):
        try:
            tid = store.task(
                pid,
                body.title,
                body.spec,
                body.checks,
                body.dependencies,
                body.priority,
            )
        except Exception as exc:
            raise HTTPException(
                400, "Invalid project, checks, or dependencies"
            ) from exc
        return {"id": tid}

    @app.post("/api/tasks/{tid}/retry")
    def retry(tid: str):
        with mutex:
            if app.state.thread and app.state.thread.is_alive():
                raise HTTPException(409, "Stop controller before requeuing tasks")
            with store.db() as db:
                row = db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
            if not row or row["status"] != "blocked":
                raise HTTPException(409, "Only blocked tasks can be retried")
            store.update(tid, status="queued", available=0, error=None)
        return {"status": "queued"}

    @app.post("/api/controller/start")
    def start(body: StartInput):
        if not body.approve_codex_usage:
            raise HTTPException(
                400,
                "Explicit approval of Codex usage and trusted acceptance commands is required",
            )
        with mutex:
            if app.state.thread and app.state.thread.is_alive():
                raise HTTPException(409, "Controller already running")
            if (store.home / "STOP").exists():
                raise HTTPException(
                    409, "STOP is set; explicitly clear it before starting"
                )
            limits = Limits(**body.model_dump(exclude={"approve_codex_usage"}))
            controller = Controller(store, limits)
            app.state.controller = controller

            def run():
                try:
                    controller.run()
                except Exception as exc:
                    store.event(None, "Controller", "failure", error=str(exc))

            thread = threading.Thread(target=run, daemon=True)
            app.state.thread = thread
            thread.start()
        return {"status": "starting"}

    @app.post("/api/controller/stop")
    def stop():
        (store.home / "STOP").touch()
        if app.state.controller:
            app.state.controller.stop.set()
        return {"status": "stopping"}

    @app.post("/api/controller/clear-stop")
    def clear_stop():
        if app.state.thread and app.state.thread.is_alive():
            raise HTTPException(409, "Wait for the active controller to stop")
        (store.home / "STOP").unlink(missing_ok=True)
        return {"status": "idle"}

    @app.get("/api/artifacts/{name:path}")
    def artifact(name: str):
        base = (store.home / "artifacts").resolve()
        path = (base / name).resolve()
        if not path.is_relative_to(base) or not path.is_file() or path.is_symlink():
            raise HTTPException(404)
        return FileResponse(
            path, filename=path.name, media_type="application/octet-stream"
        )

    app.include_router(automation_router(automation))

    if dashboard and dashboard.is_dir():
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")
    return app
