"""FastAPI application factory for the Atlas Flow backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_flow import __version__
from atlas_flow.api.websocket import router as ws_router
from atlas_flow.config import AtlasFlowConfig
from atlas_flow.execution.persistence import Persistence
from atlas_flow.execution.scheduler import Scheduler
from atlas_flow.goals.loader import resolve_project
from atlas_flow.harness.engine import Harness
from atlas_flow.harness.runner import DummyRunner
from atlas_flow.runners.cli import CliRunner
from atlas_flow.verification.gates import GateCoordinator


def _find_project_root() -> Path:
    here = Path(__file__).resolve().parent
    for parent in here.parents:
        if (parent / "PROJECT_MANIFEST.yaml").is_file():
            return parent
    return Path.cwd()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = AtlasFlowConfig.load(_find_project_root())
    db = Persistence()
    await db.initialize()
    scheduler = Scheduler(db)
    harness = Harness(db)
    harness.register(DummyRunner("dummy"))
    harness.register(CliRunner("cmd"))
    gates = GateCoordinator(db)

    app.state.config = config
    app.state.persistence = db
    app.state.scheduler = scheduler
    app.state.harness = harness
    app.state.gates = gates
    app.state.project_root = _find_project_root()

    yield

    await db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas Flow", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(ws_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/project")
    def get_project() -> dict[str, object]:
        ctx = resolve_project(_find_project_root())
        return {
            "id": ctx.project.id,
            "types": ctx.project.types,
            "phases": len(ctx.phases),
            "agents": ctx.agents.agents,
            "skills": ctx.skills.skills,
        }

    @app.get("/api/config")
    def get_config() -> dict[str, object]:
        config = app.state.config
        return {
            "autonomy_mode": config.autonomy_mode,
            "max_parallel_tasks": config.max_parallel_tasks,
            "max_retries_per_task": config.max_retries_per_task,
            "log_level": config.log_level,
            "worktree_strategy": config.worktree_strategy,
        }

    return app
