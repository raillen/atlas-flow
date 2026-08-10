"""FastAPI application factory for the Atlas Flow backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_flow import __version__
from atlas_flow.api.routes import router as api_router
from atlas_flow.api.websocket import broadcast_domain_event
from atlas_flow.api.websocket import router as ws_router
from atlas_flow.config import AtlasFlowConfig
from atlas_flow.discuss.store import DiscussionStore
from atlas_flow.execution.goal_runner import worktree_manager_for
from atlas_flow.execution.persistence import Persistence
from atlas_flow.execution.scheduler import Scheduler
from atlas_flow.goals.loader import resolve_project
from atlas_flow.harness.engine import Harness
from atlas_flow.harness.runner import DummyRunner
from atlas_flow.runners.cli import CliRunner
from atlas_flow.verification.gates import GateCoordinator

# The desktop client is served by Vite in development; the backend accepts it
# explicitly rather than allowing every origin, since it exposes local files.
DEV_ORIGINS = ["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost"]


def _find_project_root() -> Path:
    here = Path(__file__).resolve().parent
    for parent in here.parents:
        if (parent / "PROJECT_MANIFEST.yaml").is_file():
            return parent
    return Path.cwd()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    root = _find_project_root()
    config = AtlasFlowConfig.load(root)
    db = Persistence.from_config(config)
    await db.initialize()
    db.subscribe(broadcast_domain_event)

    discussions = DiscussionStore(db)
    await discussions.initialize()

    harness = Harness(db)
    harness.register(DummyRunner("dummy"))
    harness.register(CliRunner("cmd"))

    app.state.config = config
    app.state.persistence = db
    app.state.scheduler = Scheduler(db)
    app.state.harness = harness
    app.state.gates = GateCoordinator(db)
    app.state.discussions = discussions
    app.state.worktrees = worktree_manager_for(config, root)
    app.state.project_root = root
    # Background run tasks are kept referenced so they are not garbage
    # collected mid-run, which would cancel them silently.
    app.state.background = set()

    try:
        yield
    finally:
        await db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas Flow", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.include_router(ws_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/project")
    def get_project() -> dict[str, Any]:
        root = _find_project_root()
        ctx = resolve_project(root)
        return {
            "id": ctx.project.id,
            "types": ctx.project.types,
            "phases": len(ctx.phases),
            "agents": ctx.agents.agents,
            "skills": ctx.skills.skills,
            "runners": app.state.harness.runners(),
        }

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        config = app.state.config
        return {
            "autonomy_mode": config.autonomy_mode,
            "max_parallel_tasks": config.max_parallel_tasks,
            "max_retries_per_task": config.max_retries_per_task,
            "log_level": config.log_level,
            "worktree_strategy": config.worktree_strategy,
            "database_path": str(config.database_path),
        }

    return app
