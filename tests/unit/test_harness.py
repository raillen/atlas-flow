"""P04 Harness and runner tests."""

import pytest

from atlas_flow.execution.models import (
    AttemptState,
    EventType,
    Run,
    RunState,
    Task,
    TaskState,
)
from atlas_flow.execution.persistence import Persistence
from atlas_flow.harness.runner import (
    DummyRunner,
    Runner,
    RunnerCapability,
    RunnerConfig,
    RunnerResult,
)


class FailingRunner(Runner):
    """Runner whose process raises, to exercise the failure path."""

    def __init__(self, name: str = "failing") -> None:
        super().__init__(name, list(RunnerCapability))

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        raise RuntimeError("runner exploded")

    async def cancel(self, task_id: str) -> bool:
        return True


class LimitedRunner(Runner):
    """Runner that cannot surface permissions, to exercise negotiation."""

    def __init__(self, name: str = "limited") -> None:
        super().__init__(name, [RunnerCapability.TRANSCRIPT])

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        return RunnerResult(task_id=task_id, success=True)

    async def cancel(self, task_id: str) -> bool:
        return True


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
    async def test_execute_through_harness(self, db: Persistence) -> None:
        from atlas_flow.harness.engine import Harness

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

        result, attempt = await harness.execute("test-runner", task, "Run this")
        assert result.success
        assert "Dummy executed" in result.output

        # The attempt must be readable back from the database — the scorecard
        # and the Build screen both read attempts, not in-memory objects.
        stored = await db.load_attempts_for_task(task.id)
        assert [a.id for a in stored] == [attempt.id]
        assert stored[0].state == AttemptState.COMPLETED
        assert stored[0].runner == "test-runner"
        assert stored[0].completed_at is not None

        reloaded_task = (await db.load_tasks(run.id))[0]
        assert reloaded_task.state == TaskState.RUNNING

        types = {e.type for e in await db.load_events(run.id)}
        assert EventType.ATTEMPT_STARTED in types
        assert EventType.ATTEMPT_COMPLETED in types

    async def test_failing_runner_records_failed_attempt(self, db: Persistence) -> None:
        from atlas_flow.harness.engine import Harness

        harness = Harness(db)
        harness.register(FailingRunner("broken"))

        run = Run(project_id="atlas-flow", goal_id="G1", goal_revision="abc")
        await db.save_run(run)
        task = Task(run_id=run.id, objective="Test task", state=TaskState.READY)
        await db.save_task(task)

        result, attempt = await harness.execute("broken", task, "Run this")
        assert not result.success

        stored = await db.load_attempts_for_task(task.id)
        assert stored[0].state == AttemptState.FAILED
        assert stored[0].error_msg == "runner exploded"
        assert attempt.error_msg == "runner exploded"

    async def test_capability_negotiation_rejects_incapable_runner(self, db: Persistence) -> None:
        from atlas_flow.harness.engine import CapabilityError, Harness

        harness = Harness(db)
        harness.register(LimitedRunner("limited"))

        run = Run(project_id="atlas-flow", goal_id="G1", goal_revision="abc")
        await db.save_run(run)
        task = Task(run_id=run.id, objective="Needs permissions", state=TaskState.READY)
        await db.save_task(task)

        with pytest.raises(CapabilityError, match="permissions"):
            await harness.execute(
                "limited", task, "prompt", required=[RunnerCapability.PERMISSIONS]
            )

    async def test_select_runner_picks_a_capable_one(self, db: Persistence) -> None:
        from atlas_flow.harness.engine import CapabilityError, Harness

        harness = Harness(db)
        harness.register(LimitedRunner("limited"))
        harness.register(DummyRunner("full"))

        chosen = harness.select_runner([RunnerCapability.PERMISSIONS])
        assert chosen.name == "full"

        harness_without = Harness(db)
        harness_without.register(LimitedRunner("limited"))
        with pytest.raises(CapabilityError, match="No registered runner"):
            harness_without.select_runner([RunnerCapability.PERMISSIONS])

    async def test_cancel_unknown_runner(self, db: Persistence) -> None:
        from atlas_flow.harness.engine import Harness

        harness = Harness(db)

        task = Task(
            run_id="irrelevant",
            objective="x",
            state=TaskState.READY,
        )

        with pytest.raises(ValueError, match="Unknown runner"):
            await harness.execute("nonexistent", task, "prompt")
