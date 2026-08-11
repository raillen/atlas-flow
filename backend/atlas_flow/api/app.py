"""FastAPI application factory for the Atlas Flow backend."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_flow import __version__
from atlas_flow.api.routes import router as api_router
from atlas_flow.api.websocket import broadcast_agent_event, broadcast_domain_event
from atlas_flow.api.websocket import router as ws_router
from atlas_flow.config import AtlasFlowConfig
from atlas_flow.discuss.store import DiscussionStore
from atlas_flow.execution.goal_runner import worktree_manager_for
from atlas_flow.execution.persistence import Persistence
from atlas_flow.execution.scheduler import Scheduler
from atlas_flow.goals.loader import resolve_project
from atlas_flow.harness.engine import Harness
from atlas_flow.harness.runner import DummyRunner
from atlas_flow.mcp.registry import McpRegistry
from atlas_flow.routing.discovery import ModelRegistry
from atlas_flow.routing.router import ModelRouter
from atlas_flow.routing.store import RoutingStore
from atlas_flow.runners.acp import AcpRunner
from atlas_flow.runners.cli import CliRunner
from atlas_flow.verification.gates import GateCoordinator

# The desktop client is served by Vite in development; the backend accepts it
# explicitly rather than allowing every origin, since it exposes local files.
DEV_ORIGINS = ["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost"]


def _find_project_root() -> Path:
    """The project Atlas Flow is operating on — never the one it ships from.

    Resolution starts at the working directory, not at this file: an installed
    Atlas Flow would otherwise walk up to its own source tree and serve its own
    Goals to somebody else's project.
    """
    override = os.environ.get("ATLAS_FLOW_PROJECT_ROOT")
    if override:
        return Path(override).resolve()

    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "PROJECT_MANIFEST.yaml").is_file():
            return candidate
    return here


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    root = _find_project_root()
    config = AtlasFlowConfig.load(root)
    db = Persistence.from_config(config)
    await db.initialize()
    db.subscribe(broadcast_domain_event)

    discussions = DiscussionStore(db)
    await discussions.initialize()

    routing_store = RoutingStore(db)
    await routing_store.initialize()

    # Carry forward what previous runs observed, then ask the live registry
    # which models are reachable — in the background, because that probe costs
    # a multi-second subprocess round-trip and nothing should wait on it to
    # serve a request. Until it answers, routing uses the policy roster.
    router = ModelRouter()
    await routing_store.restore(router.scorecard)
    registry = ModelRegistry(router)

    harness = Harness(db, config.project_id)
    harness.register(DummyRunner("dummy"))
    harness.register(CliRunner("cmd"))

    # An ACP agent is registered only when one is configured: there is no
    # sensible default agent to guess at, and a runner that cannot start is
    # worse than one that is absent.
    mcp = McpRegistry.load(config)
    if config.acp_agent_command:
        harness.register(
            AcpRunner(
                list(config.acp_agent_command),
                name="acp",
                cwd=str(root),
                mcp=mcp,
                on_event=broadcast_agent_event,
            )
        )

    app.state.config = config
    app.state.persistence = db
    app.state.scheduler = Scheduler(db, config.project_id)
    app.state.harness = harness
    app.state.gates = GateCoordinator(db)
    app.state.discussions = discussions
    app.state.router = router
    app.state.routing_store = routing_store
    app.state.registry = registry
    app.state.mcp = mcp
    app.state.worktrees = worktree_manager_for(config, root)
    app.state.project_root = root
    # Background run tasks are kept referenced so they are not garbage
    # collected mid-run, which would cancel them silently.
    app.state.background = set()

    probe = registry.start_background_probe()
    if probe is not None:
        app.state.background.add(probe)
        probe.add_done_callback(app.state.background.discard)

    try:
        yield
    finally:
        # Anything still in flight — a run, the registry probe — is cancelled
        # and awaited before the database closes. Abandoning them leaves tasks
        # holding a connection that is about to disappear, which surfaces later
        # as "Event loop is closed" from an unrelated place.
        await _shutdown_background(app.state.background)
        await db.close()


async def _shutdown_background(tasks: set[asyncio.Task[Any]]) -> None:
    pending = [task for task in tasks if not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    tasks.clear()


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
        ctx = resolve_project(app.state.project_root)
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
