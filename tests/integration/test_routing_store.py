"""P08 durable routing memory: observations survive a restart, and every route
decision can be explained after the fact."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from atlas_flow.execution.persistence import Persistence
from atlas_flow.routing.router import ModelRouter
from atlas_flow.routing.store import RoutingStore


@pytest_asyncio.fixture
async def store(db: Persistence) -> AsyncIterator[RoutingStore]:
    routing = RoutingStore(db)
    await routing.initialize()
    yield routing


@pytest.mark.asyncio
class TestObservations:
    async def test_stats_aggregate_successes_failures_and_latency(
        self, store: RoutingStore
    ) -> None:
        await store.record_observation("mimo-v2.5-pro", True, latency_ms=100)
        await store.record_observation("mimo-v2.5-pro", True, latency_ms=300)
        await store.record_observation("mimo-v2.5-pro", False, latency_ms=200)
        await store.record_observation("gpt-5.6-luna", True, latency_ms=50)

        stats = {s.model_key: s for s in await store.stats()}

        mimo = stats["mimo-v2.5-pro"]
        assert (mimo.uses, mimo.successes, mimo.failures) == (3, 2, 1)
        assert mimo.success_rate == pytest.approx(2 / 3)
        assert mimo.average_latency_ms == pytest.approx(200.0)
        assert stats["gpt-5.6-luna"].uses == 1

    async def test_an_unobserved_model_has_no_row_rather_than_a_zero_row(
        self, store: RoutingStore
    ) -> None:
        assert await store.stats() == []


@pytest.mark.asyncio
class TestRestore:
    async def test_a_fresh_scorecard_is_seeded_from_what_earlier_runs_saw(
        self, tmp_path: Path
    ) -> None:
        """The scorecard only earns its keep if it outlives the process."""
        database = tmp_path / "state.db"

        first = Persistence(database)
        await first.initialize()
        writer = RoutingStore(first)
        await writer.initialize()
        for success in (True, True, True, False):
            await writer.record_observation("mimo-v2.5-pro", success)
        await first.close()

        # A new process: new connection, new router, empty scorecard.
        second = Persistence(database)
        await second.initialize()
        try:
            reader = RoutingStore(second)
            await reader.initialize()
            router = ModelRouter()
            assert router.scorecard.total_uses("mimo-v2.5-pro") == 0

            await reader.restore(router.scorecard)

            assert router.scorecard.total_uses("mimo-v2.5-pro") == 4
            assert router.scorecard.success_rate("mimo-v2.5-pro") == pytest.approx(0.75)
        finally:
            await second.close()


@pytest.mark.asyncio
class TestDecisions:
    async def test_a_decision_is_recoverable_with_its_candidates_and_reason(
        self, store: RoutingStore
    ) -> None:
        router = ModelRouter()
        decision = router.route("core-implementer")
        await store.record_decision(decision, task_id="task-1", run_id="run-1")

        recorded = await store.decisions_for_run("run-1")

        assert len(recorded) == 1
        entry = recorded[0]
        assert entry["task_id"] == "task-1"
        assert entry["role"] == "core-implementer"
        assert entry["selected"] == "mimo-v2.5-pro"
        assert entry["candidates"] == ["mimo-v2.5-pro", "deepseek-v4-pro"]
        assert "core-implementer" in str(entry["reason"])

    async def test_decisions_are_scoped_to_their_run(
        self, store: RoutingStore
    ) -> None:
        router = ModelRouter()
        await store.record_decision(router.route("tester"), "task-a", "run-1")
        await store.record_decision(router.route("tester"), "task-b", "run-2")

        assert [d["task_id"] for d in await store.decisions_for_run("run-2")] == ["task-b"]

    async def test_an_unroutable_role_is_still_recorded_as_a_decision(
        self, store: RoutingStore
    ) -> None:
        """Why nothing was chosen is exactly the question worth answering."""
        router = ModelRouter(available_models=["some/unrelated-model"])
        decision = router.route("reviewer")
        assert decision.selected is None

        await store.record_decision(decision, "task-1", "run-1")

        entry = (await store.decisions_for_run("run-1"))[0]
        assert entry["selected"] is None
        assert "No reachable model" in str(entry["reason"])
