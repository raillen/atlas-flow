"""P09 performance budgets, measured rather than asserted in prose.

The budgets are the ones in docs/04-quality/PERFORMANCE_BUDGETS.md. These
measure the two that are the runtime's own responsibility — appending an event
and answering the queries the desktop polls — on the machine running the suite.

A budget nobody measures is a wish. A budget measured so tightly that ordinary
scheduling noise trips it is worse, so each check uses a p95 over enough samples
that a single slow moment cannot decide the outcome, and the reported number is
printed so a regression is visible even when the assertion still passes.
"""

import statistics
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from atlas_flow.api.app import create_app
from atlas_flow.execution.models import DomainEvent, EventType
from atlas_flow.execution.persistence import Persistence
from atlas_flow.routing.discovery import DiscoveryResult, ModelRegistry

# docs/04-quality/PERFORMANCE_BUDGETS.md
EVENT_APPEND_P95_MS = 20.0
BACKEND_QUERY_P95_MS = 150.0


def p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[index]


def report(label: str, samples: list[float], budget: float) -> None:
    print(
        f"\n{label}: p95 {p95(samples):.2f}ms, median "
        f"{statistics.median(samples):.2f}ms, max {max(samples):.2f}ms "
        f"(budget {budget:.0f}ms)"
    )


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[Persistence]:
    # File-backed, because the budget is about the durable store, not a cache.
    persistence = Persistence(tmp_path / "state.db")
    await persistence.initialize()
    try:
        yield persistence
    finally:
        await persistence.close()


@pytest.fixture
def client(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
           ) -> Iterator[TestClient]:
    state = tmp_path_factory.mktemp("perf-state")
    monkeypatch.setenv("ATLAS_FLOW_STATE_DIR", str(state))
    ModelRegistry.seed(DiscoveryResult(reachable=True, reason="seeded for measurement"))
    try:
        with TestClient(create_app()) as test_client:
            yield test_client
    finally:
        ModelRegistry.reset_cache()


@pytest.mark.asyncio
async def test_event_append_stays_within_its_budget(db: Persistence) -> None:
    samples: list[float] = []
    for index in range(200):
        event = DomainEvent(
            project_id="atlas-flow",
            run_id="run-perf",
            type=EventType.STATE_CHANGE,
            payload={"index": index, "previous": "READY", "next": "RUNNING"},
        )
        started = time.perf_counter()
        await db.save_event(event)
        samples.append((time.perf_counter() - started) * 1000)

    report("event append", samples, EVENT_APPEND_P95_MS)
    assert p95(samples) < EVENT_APPEND_P95_MS


@pytest.mark.asyncio
async def test_reading_a_long_event_log_stays_within_the_query_budget(
    db: Persistence,
) -> None:
    """The Build screen reloads the whole log on every poll."""
    for index in range(1000):
        await db.save_event(
            DomainEvent(
                project_id="atlas-flow",
                run_id="run-perf",
                type=EventType.STATE_CHANGE,
                payload={"index": index},
            )
        )

    samples: list[float] = []
    for _ in range(20):
        started = time.perf_counter()
        events = await db.load_events("run-perf")
        samples.append((time.perf_counter() - started) * 1000)
    assert len(events) == 1000

    report("load 1000 events", samples, BACKEND_QUERY_P95_MS)
    assert p95(samples) < BACKEND_QUERY_P95_MS


class TestApiLatency:
    def test_the_endpoints_the_desktop_polls_answer_within_budget(
        self, client: TestClient
    ) -> None:
        run_id = client.post(
            "/api/runs", json={"goal_id": "P01-G01", "runner": "dummy"}
        ).json()["id"]

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if client.get(f"/api/runs/{run_id}").json()["run"]["state"] in (
                "VERIFYING", "COMPLETED", "FAILED", "BLOCKED", "REVIEWING"
            ):
                break
            time.sleep(0.05)

        for path in (f"/api/runs/{run_id}", "/api/goals", "/api/routing"):
            samples: list[float] = []
            for _ in range(20):
                started = time.perf_counter()
                response = client.get(path)
                samples.append((time.perf_counter() - started) * 1000)
                assert response.status_code == 200

            report(path, samples, BACKEND_QUERY_P95_MS)
            assert p95(samples) < BACKEND_QUERY_P95_MS
