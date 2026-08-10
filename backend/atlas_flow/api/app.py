"""FastAPI application factory for the Atlas Flow backend."""

from fastapi import FastAPI

from atlas_flow import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas Flow", version=__version__)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
