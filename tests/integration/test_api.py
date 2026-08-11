"""P06 API surface: the desktop reads real state through these endpoints."""

import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from atlas_flow import __version__
from atlas_flow.api.app import create_app
from atlas_flow.routing.discovery import DiscoveryResult, ModelRegistry
from atlas_flow.routing.router import ModelRouter

# What the live registry would have answered. Seeding it keeps every app in
# this module from spawning `cmd --list-models`; the probe itself is covered
# by tests/unit/test_discovery.py.
SEEDED_MODELS = ["deepseek/deepseek-v4-pro", "xiaomi/mimo-v2.5-pro", "gpt-5.6-luna"]


@pytest.fixture
def client(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
           ) -> Iterator[TestClient]:
    """A client whose operational state lives in a throwaway directory."""
    state = tmp_path_factory.mktemp("atlas-state")
    monkeypatch.setenv("ATLAS_FLOW_STATE_DIR", str(state))
    ModelRegistry.seed(
        DiscoveryResult(
            available=list(SEEDED_MODELS),
            reachable=True,
            reason="seeded by the test suite",
            probed_at="2026-01-01T00:00:00+00:00",
        )
    )
    try:
        with TestClient(create_app()) as test_client:
            yield test_client
    finally:
        ModelRegistry.reset_cache()


TERMINAL_RUN_STATES = {"VERIFYING", "REVIEWING", "COMPLETED", "FAILED", "BLOCKED"}


def wait_for_run(client: TestClient, run_id: str, timeout: float = 10.0) -> dict:
    """Poll a run until it stops moving.

    Starting a run returns as soon as it is scheduled, so anything that
    inspects its results has to wait for it the same way the desktop does.
    """
    deadline = time.monotonic() + timeout
    detail: dict = {}
    while time.monotonic() < deadline:
        detail = client.get(f"/api/runs/{run_id}").json()
        if detail["run"]["state"] in TERMINAL_RUN_STATES:
            return detail
        time.sleep(0.05)
    raise AssertionError(f"Run {run_id} did not finish: {detail.get('run')}")


class TestHealthAndProject:
    def test_healthz_reports_ok(self, client: TestClient) -> None:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": __version__}

    def test_project_exposes_registries_and_runners(self, client: TestClient) -> None:
        body = client.get("/api/project").json()
        assert body["id"] == "atlas-flow"
        assert "goal-planner" in body["agents"]
        assert set(body["runners"]) >= {"cmd", "dummy"}

    def test_config_reports_a_durable_database_path(self, client: TestClient) -> None:
        body = client.get("/api/config").json()
        assert body["database_path"].endswith("state.db")
        assert ":memory:" not in body["database_path"]


class TestGoals:
    def test_goals_come_from_git_not_from_the_database(self, client: TestClient) -> None:
        goals = client.get("/api/goals").json()
        assert len(goals) == 11
        by_id = {g["id"]: g for g in goals}
        assert by_id["P05-G01"]["title"] == "Goal Planner and DAG Execution"
        assert by_id["P05-G01"]["gates"]["build"] == "required"

    def test_unknown_goal_is_404(self, client: TestClient) -> None:
        assert client.get("/api/goals/P99-G01").status_code == 404

    def test_verification_reports_gates_and_blocking_reason(
        self, client: TestClient
    ) -> None:
        body = client.get("/api/goals/P05-G01/verification").json()
        assert body["goal_id"] == "P05-G01"
        assert {g["gate"] for g in body["gates"]} == {
            "build", "tests", "review", "documentation"
        }
        # No evidence has been recorded in this throwaway database.
        assert body["completable"] is False
        assert "required gate" in body["blocking"]


class TestRuns:
    def test_runs_start_empty(self, client: TestClient) -> None:
        assert client.get("/api/runs").json() == []

    def test_creating_a_run_executes_the_goal_and_exposes_its_state(
        self, client: TestClient
    ) -> None:
        created = client.post(
            "/api/runs", json={"goal_id": "P01-G01", "runner": "dummy"}
        )
        assert created.status_code == 202
        run_id = created.json()["id"]

        listed = client.get("/api/runs").json()
        assert [r["id"] for r in listed] == [run_id]

        detail = wait_for_run(client, run_id)
        assert detail["run"]["goal_id"] == "P01-G01"
        # One task per acceptance criterion of P01-G01.
        assert len(detail["tasks"]) == 4
        assert all(task["objective"] for task in detail["tasks"])
        assert {task["state"] for task in detail["tasks"]} == {"SUCCEEDED"}

        events = client.get(f"/api/runs/{run_id}/events").json()
        assert any(e["type"] == "atlas.run.started" for e in events)
        assert any(e["type"] == "atlas.task.succeeded" for e in events)

    def test_run_produces_attempts_and_evidence(self, client: TestClient) -> None:
        run_id = client.post(
            "/api/runs", json={"goal_id": "P01-G01", "runner": "dummy"}
        ).json()["id"]

        detail = wait_for_run(client, run_id)
        assert len(detail["attempts"]) == len(detail["tasks"])
        assert {a["runner"] for a in detail["attempts"]} == {"dummy"}
        assert all(a["state"] == "COMPLETED" for a in detail["attempts"])

        verification = client.get("/api/goals/P01-G01/verification").json()
        assert any(e["verdict"] == "PASSED" for e in verification["evidence"])
        build_gate = next(g for g in verification["gates"] if g["gate"] == "build")
        assert build_gate["verdict"] == "PASSED"

    def test_unknown_goal_cannot_start_a_run(self, client: TestClient) -> None:
        response = client.post("/api/runs", json={"goal_id": "P99-G01"})
        assert response.status_code == 404

    def test_unknown_runner_is_rejected_with_the_available_list(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/runs", json={"goal_id": "P01-G01", "runner": "nope"}
        )
        assert response.status_code == 400
        assert "dummy" in response.json()["detail"]

    def test_unknown_run_is_404(self, client: TestClient) -> None:
        assert client.get("/api/runs/run-nope").status_code == 404


class TestRouting:
    def test_routing_reports_the_live_registry_and_every_role(
        self, client: TestClient
    ) -> None:
        body = client.get("/api/routing").json()

        assert body["state"] == "reachable"
        assert body["degraded"] is False
        assert body["available"] == SEEDED_MODELS
        roles = {r["role"]: r for r in body["roles"]}
        assert set(roles) == set(ModelRouter.ROLE_DEFAULTS)
        # Every route carries its own explanation; the UI never has to guess.
        assert all(r["explanation"] for r in roles.values())
        assert roles["reviewer"]["selected"] == "deepseek-v4-pro"
        assert roles["reviewer"]["provider"] == "deepseek"

    def test_routing_stats_are_empty_until_a_run_observes_something(
        self, client: TestClient
    ) -> None:
        assert client.get("/api/routing").json()["stats"] == []

    def test_a_run_records_why_each_task_got_its_model(
        self, client: TestClient
    ) -> None:
        run_id = client.post(
            "/api/runs", json={"goal_id": "P01-G01", "runner": "dummy"}
        ).json()["id"]
        detail = wait_for_run(client, run_id)

        decisions = client.get(f"/api/runs/{run_id}/routing").json()
        assert len(decisions) == len(detail["tasks"])
        assert {d["task_id"] for d in decisions} == {t["id"] for t in detail["tasks"]}
        assert all(d["selected"] for d in decisions)
        assert all(d["reason"] for d in decisions)

        stats = {s["model_key"]: s for s in client.get("/api/routing").json()["stats"]}
        assert sum(s["uses"] for s in stats.values()) == len(detail["tasks"])
        assert all(s["success_rate"] == 1.0 for s in stats.values())

    def test_run_routing_for_an_unknown_run_is_empty_not_an_error(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/runs/run-nope/routing")
        assert response.status_code == 200
        assert response.json() == []


class TestDiscussions:
    def test_a_discussion_accumulates_a_durable_ledger(self, client: TestClient) -> None:
        session_id = client.post("/api/discussions").json()["session_id"]

        client.post(
            f"/api/discussions/{session_id}/messages",
            json={"content": "We should use Python"},
        )
        decision_id = client.post(
            f"/api/discussions/{session_id}/decisions",
            json={
                "title": "Python backend",
                "statement": "The core is Python",
                "rationale": "Reuses Project Atlas tooling",
                "requires_adr": True,
            },
        ).json()["id"]

        accepted = client.post(
            f"/api/discussions/{session_id}/decisions/{decision_id}/accept"
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "ACCEPTED"

        reloaded = client.get(f"/api/discussions/{session_id}").json()
        assert len(reloaded["messages"]) == 1
        assert reloaded["decisions"][0]["status"] == "ACCEPTED"
        assert session_id in client.get("/api/discussions").json()

    def test_accepting_twice_is_a_conflict(self, client: TestClient) -> None:
        session_id = client.post("/api/discussions").json()["session_id"]
        decision_id = client.post(
            f"/api/discussions/{session_id}/decisions",
            json={"title": "T", "statement": "S", "rationale": "R"},
        ).json()["id"]

        client.post(f"/api/discussions/{session_id}/decisions/{decision_id}/accept")
        again = client.post(
            f"/api/discussions/{session_id}/decisions/{decision_id}/accept"
        )
        assert again.status_code == 409

    def test_finalizing_an_incomplete_draft_is_refused(self, client: TestClient) -> None:
        session_id = client.post("/api/discussions").json()["session_id"]
        response = client.post(f"/api/discussions/{session_id}/finalize")

        assert response.status_code == 409
        assert "Not ready" in response.json()["detail"]

    def test_unknown_discussion_is_404(self, client: TestClient) -> None:
        assert client.get("/api/discussions/nope").status_code == 404
        assert (
            client.post("/api/discussions/nope/messages", json={"content": "x"}).status_code
            == 404
        )


class TestEventStream:
    def test_run_events_reach_a_connected_client(self, client: TestClient) -> None:
        """The desktop follows a run over the socket, not by polling alone."""
        with client.websocket_connect("/ws/session-1") as socket:
            run_id = client.post(
                "/api/runs", json={"goal_id": "P01-G01", "runner": "dummy"}
            ).json()["id"]
            wait_for_run(client, run_id)

            # Events arrive in commit order, so read until the run is
            # accounted for rather than guessing how many there will be.
            received: list[str] = []
            while "atlas.run.completed" not in received and len(received) < 60:
                message = socket.receive_json()
                received.append(message["type"])
                if message["type"] == "atlas.task.succeeded":
                    break

        assert received[0] == "atlas.run.started"
        assert any(t.startswith("atlas.attempt.") for t in received)
        assert "atlas.task.succeeded" in received

    def test_malformed_message_is_reported_not_crashed(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/session-2") as socket:
            socket.send_text("this is not json")
            assert socket.receive_json()["type"] == "atlas.error"


class TestDocs:
    def test_docs_are_listed_by_section(self, client: TestClient) -> None:
        entries = client.get("/api/docs").json()
        by_path = {e["path"]: e for e in entries}
        assert "01-architecture/SYSTEM_OVERVIEW.md" in by_path
        assert by_path["01-architecture/SYSTEM_OVERVIEW.md"]["section"] == "Architecture"
        assert by_path["01-architecture/SYSTEM_OVERVIEW.md"]["title"]

    def test_doc_content_is_readable(self, client: TestClient) -> None:
        body = client.get("/api/docs/01-architecture/SYSTEM_OVERVIEW.md").json()
        assert body["content"].startswith("#")

    def test_path_traversal_is_refused(self, client: TestClient) -> None:
        """A crafted path must not read outside docs/."""
        for attempt in (
            "../PROJECT_MANIFEST.yaml",
            "../../etc/passwd",
            "..%2f..%2fPROJECT_MANIFEST.yaml",
        ):
            assert client.get(f"/api/docs/{attempt}").status_code == 404

    def test_non_markdown_is_refused(self, client: TestClient) -> None:
        assert client.get("/api/docs/_meta/knowledge-graph.json").status_code == 404
