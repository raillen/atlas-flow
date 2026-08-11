"""API scaffold smoke test."""

from pathlib import Path

from fastapi.testclient import TestClient

from atlas_flow import __version__
from atlas_flow.api.app import create_app


def test_healthz_reports_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_settings_document_lists_scopes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ATLAS_FLOW_PROJECT_ROOT", str(tmp_path))
    with TestClient(create_app()) as client:
        response = client.get("/api/settings")

        assert response.status_code == 200
        document = response.json()
        assert "settings" in document
        assert "providers" in document
        scopes = {setting["source"]["scope"] for setting in document["settings"]}
        assert scopes == {"project", "user"}


def test_settings_save_writes_user_scope_and_reports_restart(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ATLAS_FLOW_PROJECT_ROOT", str(tmp_path))
    # Isolate the user file: it lives in $HOME, not the project, and the real
    # one must never be touched by tests.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    with TestClient(create_app()) as client:
        response = client.put(
            "/api/settings",
            json={"scope": "user", "values": {"log_level": "DEBUG"}},
        )

        assert response.status_code == 200
        payload = response.json()
        assert "log_level" in payload["changed"]
        assert payload["restart_required"] is True
        assert (home / ".atlas-flow.yaml").is_file()


def test_settings_save_rejects_foreign_scope_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ATLAS_FLOW_PROJECT_ROOT", str(tmp_path))
    with TestClient(create_app()) as client:
        response = client.put(
            "/api/settings",
            json={"scope": "user", "values": {"max_parallel_tasks": 9}},
        )

        assert response.status_code == 409
        assert "max_parallel_tasks" in response.json()["detail"]
