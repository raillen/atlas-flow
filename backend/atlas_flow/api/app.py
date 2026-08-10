"""FastAPI application factory for the Atlas Flow backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_flow import __version__
from atlas_flow.api.websocket import router as ws_router
from atlas_flow.goals.loader import resolve_project


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas Flow", version=__version__)
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
        from pathlib import Path
        ctx = resolve_project(Path.cwd())
        return {
            "id": ctx.project.id,
            "types": ctx.project.types,
            "phases": len(ctx.phases),
            "agents": ctx.agents.agents,
            "skills": ctx.skills.skills,
        }

    return app
