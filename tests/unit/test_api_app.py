"""API scaffold smoke test."""

from fastapi.testclient import TestClient

from atlas_flow import __version__
from atlas_flow.api.app import create_app


def test_healthz_reports_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
