"""P04 Harness and runner tests."""

import pytest

from atlas_flow.execution.models import Run, RunState, Task, TaskState
from atlas_flow.execution.persistence import Persistence
from atlas_flow.harness.runner import (
    DummyRunner,
    RunnerCapability,
    RunnerConfig,
)


class TestRunnerCapabilities:
    def test_dummy_runner_has_all_capabilities(self) -> None:
        r = DummyRunner()
        assert r.has_capability(RunnerCapability.AGENT_SESSION)
        assert r.has_capability(RunnerCapability.CANCELLATION)
        assert r.has_capability(RunnerCapability.TRANSCRIPT)

    def test_negotiation_intersects_requested(self) -> None:
        r = DummyRunner()
        negotiated = r.negotiate([RunnerCapability.AGENT_SESSION, "bogus"])  # type: ignore[list-item]
        assert RunnerCapability.AGENT_SESSION in negotiated
        assert "bogus" not in negotiated


@pytest.mark.asyncio
class TestDummyRunner:
    async def test_run_returns_success(self) -> None:
        r = DummyRunner()
        result = await r.run("task-1", "do something", RunnerConfig(model="test"))
        assert result.success
        assert "Dummy executed" in result.output

    async def test_cancel_returns_true(self) -> None:
        r = DummyRunner()
        assert await r.cancel("task-1")


@pytest.mark.asyncio
class TestHarnessIntegration:
    async def test_execute_through_harness(self) -> None:
        from atlas_flow.harness.engine import Harness

        db = Persistence(":memory:")
        await db.initialize()
        harness = Harness(db)

        r = DummyRunner("test-runner")
        harness.register(r)

        run = Run(
            project_id="atlas-flow",
            goal_id="G1",
            goal_revision="abc",
            state=RunState.CREATED,
        )
        await db.save_run(run)

        task = Task(
            run_id=run.id,
            objective="Test task",
            state=TaskState.READY,
        )
        await db.save_task(task)

        result = await harness.execute("test-runner", task, "Run this")
        assert result.success
        assert "Dummy executed" in result.output

    async def test_cancel_unknown_runner(self) -> None:
        from atlas_flow.harness.engine import Harness

        db = Persistence(":memory:")
        await db.initialize()
        harness = Harness(db)

        task = Task(
            run_id="irrelevant",
            objective="x",
            state=TaskState.READY,
        )

        with pytest.raises(ValueError, match="Unknown runner"):
            await harness.execute("nonexistent", task, "prompt")
