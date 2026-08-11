"""P10: Atlas Flow run against projects that are not Atlas Flow.

The premise of the product is that it orchestrates whatever project it is
opened on. A test suite that only ever opens this repository cannot tell the
difference between a generic runtime and one that has this repository's name
baked into it — which is exactly the defect these found.
"""

import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures.atlas_project import (  # noqa: E402
    CATEGORIES,
    CLI_TOOL,
    PYTHON_LIBRARY,
    WEB_APPLICATION,
    ProjectSpec,
    write_project,
)

from atlas_flow.api.app import create_app  # noqa: E402
from atlas_flow.routing.discovery import DiscoveryResult, ModelRegistry  # noqa: E402

TERMINAL = {"VERIFYING", "REVIEWING", "COMPLETED", "FAILED", "BLOCKED"}


@pytest.fixture
def open_project(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[object]:
    """Open Atlas Flow on a freshly built project of a given category."""
    created: list[TestClient] = []

    def opener(spec: ProjectSpec) -> TestClient:
        root = write_project(tmp_path_factory.mktemp(spec.project_id) / "repo", spec)
        monkeypatch.setenv("ATLAS_FLOW_PROJECT_ROOT", str(root))
        ModelRegistry.seed(DiscoveryResult(reachable=True, reason="seeded"))
        client = TestClient(create_app())
        client.__enter__()
        created.append(client)
        return client

    try:
        yield opener
    finally:
        for client in created:
            client.__exit__(None, None, None)
        ModelRegistry.reset_cache()


def wait_for_run(client: TestClient, run_id: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    detail: dict = {}
    while time.monotonic() < deadline:
        detail = client.get(f"/api/runs/{run_id}").json()
        if detail["run"]["state"] in TERMINAL:
            return detail
        time.sleep(0.05)
    raise AssertionError(f"Run {run_id} did not finish: {detail.get('run')}")


@pytest.mark.parametrize("spec", CATEGORIES, ids=lambda s: s.project_id)
def test_atlas_flow_serves_the_project_it_was_opened_on(spec, open_project) -> None:
    client = open_project(spec)

    project = client.get("/api/project").json()
    assert project["id"] == spec.project_id
    assert project["types"] == spec.types

    goals = client.get("/api/goals").json()
    assert {goal["id"] for goal in goals} == {g.id for g in spec.goals}


@pytest.mark.parametrize("spec", CATEGORIES, ids=lambda s: s.project_id)
def test_a_goal_runs_end_to_end_in_every_category(spec, open_project) -> None:
    client = open_project(spec)
    goal = spec.goals[0]

    created = client.post("/api/runs", json={"goal_id": goal.id, "runner": "dummy"})
    assert created.status_code == 202
    detail = wait_for_run(client, created.json()["id"])

    assert detail["run"]["goal_id"] == goal.id
    assert len(detail["tasks"]) == len(goal.acceptance)
    assert {task["state"] for task in detail["tasks"]} == {"SUCCEEDED"}
    assert len(detail["attempts"]) == len(goal.acceptance)

    verification = client.get(f"/api/goals/{goal.id}/verification").json()
    build = next(g for g in verification["gates"] if g["gate"] == "build")
    assert build["verdict"] == "PASSED"
    # The other gates have no evidence, so the Goal is honestly incomplete.
    assert verification["completable"] is False


@pytest.mark.parametrize("spec", CATEGORIES, ids=lambda s: s.project_id)
def test_events_are_attributed_to_the_project_that_produced_them(
    spec, open_project
) -> None:
    """A run on somebody else's project must not be stamped 'atlas-flow'."""
    client = open_project(spec)
    goal = spec.goals[0]

    run_id = client.post(
        "/api/runs", json={"goal_id": goal.id, "runner": "dummy"}
    ).json()["id"]
    wait_for_run(client, run_id)

    events = client.get(f"/api/runs/{run_id}/events").json()
    assert events
    assert {event["project_id"] for event in events} == {spec.project_id}
    assert client.get("/api/config").json()["database_path"].endswith("state.db")


def test_dependencies_are_honoured_across_phases(open_project) -> None:
    """The second Goal depends on the first, in a project with two phases."""
    client = open_project(PYTHON_LIBRARY)

    goals = {goal["id"]: goal for goal in client.get("/api/goals").json()}
    assert goals["L02-G01"]["dependencies"] == ["L01-G01"]
    assert goals["L01-G01"]["dependencies"] == []


def test_operational_state_lands_inside_the_opened_project(open_project) -> None:
    """Not in Atlas Flow's own directory, which is where it would leak to."""
    client = open_project(CLI_TOOL)
    run_id = client.post(
        "/api/runs", json={"goal_id": "C01-G01", "runner": "dummy"}
    ).json()["id"]
    wait_for_run(client, run_id)

    database = Path(client.get("/api/config").json()["database_path"])
    assert database.is_file()
    assert database.parent.name == ".atlas-flow"
    # And the project's own repository stays clean: the state directory ignores
    # itself, so a run never shows up as uncommitted work.
    ignore = (database.parent / ".gitignore").read_text(encoding="utf-8")
    assert ignore.splitlines()[-1] == "*"


def test_two_projects_do_not_share_operational_state(open_project) -> None:
    library = open_project(PYTHON_LIBRARY)
    web = open_project(WEB_APPLICATION)

    library_db = library.get("/api/config").json()["database_path"]
    web_db = web.get("/api/config").json()["database_path"]
    assert library_db != web_db

    library.post("/api/runs", json={"goal_id": "L01-G01", "runner": "dummy"})
    assert web.get("/api/runs").json() == []


class TestFreshInstallAndRecovery:
    """The walkthrough a new user follows, executed rather than described."""

    def test_a_freshly_opened_project_starts_with_no_operational_state(
        self, tmp_path_factory: pytest.TempPathFactory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = write_project(tmp_path_factory.mktemp("fresh") / "repo", CLI_TOOL)
        assert not (root / ".atlas-flow").exists()

        monkeypatch.setenv("ATLAS_FLOW_PROJECT_ROOT", str(root))
        ModelRegistry.seed(DiscoveryResult(reachable=True, reason="seeded"))
        try:
            with TestClient(create_app()) as client:
                assert client.get("/healthz").json()["status"] == "ok"
                assert client.get("/api/runs").json() == []
                # Goals come from Git, so they are there before anything runs.
                assert client.get("/api/goals").json()
        finally:
            ModelRegistry.reset_cache()

        # Opening the project created the state directory, and it hides itself.
        assert (root / ".atlas-flow" / ".gitignore").is_file()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        )
        assert status.stdout.strip() == ""

    def test_state_from_a_previous_session_is_still_there_after_a_restart(
        self, tmp_path_factory: pytest.TempPathFactory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = write_project(tmp_path_factory.mktemp("restart") / "repo", CLI_TOOL)
        monkeypatch.setenv("ATLAS_FLOW_PROJECT_ROOT", str(root))
        ModelRegistry.seed(DiscoveryResult(reachable=True, reason="seeded"))

        try:
            with TestClient(create_app()) as first:
                run_id = first.post(
                    "/api/runs", json={"goal_id": "C01-G01", "runner": "dummy"}
                ).json()["id"]
                wait_for_run(first, run_id)

            # A second session: new process, same project directory.
            with TestClient(create_app()) as second:
                runs = second.get("/api/runs").json()
                assert [run["id"] for run in runs] == [run_id]

                detail = second.get(f"/api/runs/{run_id}").json()
                assert {task["state"] for task in detail["tasks"]} == {"SUCCEEDED"}
                assert detail["events"]

                verification = second.get("/api/goals/C01-G01/verification").json()
                assert any(e["verdict"] == "PASSED" for e in verification["evidence"])
        finally:
            ModelRegistry.reset_cache()
