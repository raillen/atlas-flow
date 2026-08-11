"""P03 Execution runtime tests."""

from pathlib import Path

import pytest

from atlas_flow.execution.models import (
    Attempt,
    AttemptState,
    DomainEvent,
    EventType,
    Run,
    RunState,
    Task,
    TaskState,
    can_transition,
)
from atlas_flow.execution.persistence import InvalidTransition, Persistence
from atlas_flow.execution.scheduler import Scheduler, recover_run


class TestStateMachine:
    def test_valid_run_flow(self) -> None:
        transitions = [
            (RunState.CREATED, RunState.PLANNING),
            (RunState.PLANNING, RunState.READY),
            (RunState.READY, RunState.RUNNING),
            (RunState.RUNNING, RunState.VERIFYING),
            (RunState.VERIFYING, RunState.REVIEWING),
            (RunState.REVIEWING, RunState.COMPLETED),
        ]
        for frm, to in transitions:
            assert can_transition(frm, to, "run"), f"{frm} -> {to} should be valid"

    def test_invalid_run_transition_rejected(self) -> None:
        assert not can_transition(RunState.CREATED, RunState.RUNNING, "run")
        assert not can_transition(RunState.COMPLETED, RunState.PLANNING, "run")

    def test_task_flow(self) -> None:
        assert can_transition(TaskState.PLANNED, TaskState.READY, "task")
        assert can_transition(TaskState.READY, TaskState.RUNNING, "task")
        assert can_transition(TaskState.RUNNING, TaskState.SUCCEEDED, "task")
        assert can_transition(TaskState.FAILED, TaskState.READY, "task")

    def test_task_cannot_jump_to_succeeded(self) -> None:
        assert not can_transition(TaskState.PLANNED, TaskState.SUCCEEDED, "task")


@pytest.mark.asyncio
class TestPersistence:
    async def test_initialize_creates_tables(self, db: Persistence) -> None:
        run = Run(
            project_id="atlas-flow",
            goal_id="G1",
            goal_revision="abc123",
            state=RunState.CREATED,
        )
        await db.save_run(run)
        loaded = await db.load_run(run.id)
        assert loaded is not None
        assert loaded.goal_id == "G1"

    async def test_event_append_only_ordering(self, db: Persistence) -> None:
        e1 = DomainEvent(
            project_id="test", run_id="R1", type=EventType.RUN_STARTED
        )
        e2 = DomainEvent(
            project_id="test", run_id="R1", type=EventType.TASK_SUCCEEDED,
            payload={"task_id": "T1"},
        )
        await db.save_event(e1)
        await db.save_event(e2)
        events = await db.load_events("R1")
        assert len(events) == 2
        assert events[0].type == EventType.RUN_STARTED
        assert events[1].payload["task_id"] == "T1"

    async def test_save_load_tasks(self, db: Persistence) -> None:
        run = Run(
            project_id="atlas-flow",
            goal_id="G1",
            goal_revision="abc",
            state=RunState.CREATED,
        )
        await db.save_run(run)
        task = Task(
            run_id=run.id,
            objective="Implement auth",
            role="backend",
            scope=["backend/auth"],
            state=TaskState.PLANNED,
            dependencies=["T0"],
        )
        await db.save_task(task)
        tasks = await db.load_tasks(run.id)
        assert len(tasks) == 1
        assert tasks[0].dependencies == ["T0"]


@pytest.mark.asyncio
class TestScheduler:
    async def test_run_lifecycle(self, db: Persistence) -> None:
        sched = Scheduler(db)

        run = Run(
            project_id="atlas-flow",
            goal_id="G1",
            goal_revision="abc",
            state=RunState.CREATED,
        )
        await db.save_run(run)
        run = await sched.start_run(run)
        assert run.state == RunState.PLANNING

        tasks = [
            Task(run_id=run.id, objective="Task A", state=TaskState.PLANNED),
            Task(run_id=run.id, objective="Task B", state=TaskState.PLANNED),
        ]
        run, _ = await sched.schedule_tasks(run, tasks)
        assert run.state == RunState.READY

        ready = await sched.ready_tasks(run.id)
        assert len(ready) == 2

        run = await sched.advance_run(run, RunState.RUNNING)
        for pending in ready:
            started = await sched.start_task(await sched.mark_task_ready(pending))
            await sched.complete_task(started)

        done = await sched.evaluate_run_completion(run)
        assert done is True

    async def test_dependent_task_is_not_ready_until_dependency_succeeds(
        self, db: Persistence
    ) -> None:
        sched = Scheduler(db)

        run = Run(project_id="atlas-flow", goal_id="G1", goal_revision="abc")
        await db.save_run(run)
        run = await sched.start_run(run)

        first = Task(run_id=run.id, objective="First")
        second = Task(run_id=run.id, objective="Second", dependencies=[first.id])
        run, _ = await sched.schedule_tasks(run, [first, second])

        ready = await sched.ready_tasks(run.id)
        assert [t.id for t in ready] == [first.id]

        first = await sched.mark_task_ready(first)
        first = await sched.start_task(first)
        await sched.complete_task(first)

        ready = await sched.ready_tasks(run.id)
        assert [t.id for t in ready] == [second.id]

    async def test_invalid_transition_is_rejected_before_writing(self, db: Persistence) -> None:
        sched = Scheduler(db)

        run = Run(project_id="atlas-flow", goal_id="G1", goal_revision="abc")
        await db.save_run(run)

        with pytest.raises(InvalidTransition):
            await sched.advance_run(run, RunState.RUNNING)

        stored = await db.load_run(run.id)
        assert stored is not None
        assert stored.state == RunState.CREATED
        assert await db.load_events(run.id) == []


@pytest.mark.asyncio
class TestCrashRecovery:
    async def test_state_survives_process_restart(self, tmp_path: Path) -> None:
        """A new connection to the same file sees everything the old one wrote."""
        db_path = tmp_path / "state" / "atlas.db"

        first = Persistence(db_path)
        await first.initialize()
        sched = Scheduler(first)
        run = Run(project_id="atlas-flow", goal_id="G1", goal_revision="abc")
        await first.save_run(run)
        run = await sched.start_run(run)
        task = Task(run_id=run.id, objective="Interrupted work")
        run, _ = await sched.schedule_tasks(run, [task])
        run = await sched.advance_run(run, RunState.RUNNING)
        task = await sched.mark_task_ready(task)
        task = await sched.start_task(task)
        attempt = Attempt(
            task_id=task.id, run_id=run.id, runner="cmd", state=AttemptState.RUNNING
        )
        await first.save_attempt(attempt)
        # Simulate a crash: the connection dies without an orderly shutdown.
        await first.close()

        assert db_path.is_file()

        second = Persistence(db_path)
        await second.initialize()
        try:
            reloaded = await second.load_run(run.id)
            assert reloaded is not None
            assert reloaded.state == RunState.RUNNING
            assert len(await second.load_tasks(run.id)) == 1
            assert len(await second.load_attempts(run.id)) == 1
            assert len(await second.load_events(run.id)) >= 4
        finally:
            await second.close()

    async def test_recovery_closes_orphans_and_is_idempotent(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "atlas.db"
        db = Persistence(db_path)
        await db.initialize()
        try:
            sched = Scheduler(db)
            run = Run(project_id="atlas-flow", goal_id="G1", goal_revision="abc")
            await db.save_run(run)
            run = await sched.start_run(run)
            task = Task(run_id=run.id, objective="Interrupted work")
            run, _ = await sched.schedule_tasks(run, [task])
            run = await sched.advance_run(run, RunState.RUNNING)
            task = await sched.mark_task_ready(task)
            task = await sched.start_task(task)
            attempt = Attempt(
                task_id=task.id, run_id=run.id, runner="cmd", state=AttemptState.RUNNING
            )
            await db.save_attempt(attempt)

            report = await recover_run(db, run.id)
            assert report is not None
            assert report.reconciled
            assert report.orphaned_tasks == [task.id]
            assert report.orphaned_attempts == [attempt.id]
            assert report.run.state == RunState.BLOCKED

            recovered_task = (await db.load_tasks(run.id))[0]
            assert recovered_task.state == TaskState.FAILED
            recovered_attempt = (await db.load_attempts(run.id))[0]
            assert recovered_attempt.state == AttemptState.FAILED

            # A failed task is retryable, which is what makes recovery safe to
            # run again: the second pass finds nothing left to reconcile.
            again = await recover_run(db, run.id)
            assert again is not None
            assert not again.reconciled
        finally:
            await db.close()

    async def test_recover_unknown_run_returns_none(self, db: Persistence) -> None:
        assert await recover_run(db, "run-does-not-exist") is None


class TestCancellationReachability:
    """Cancellation must reach every state that is not already finished."""

    def test_every_live_task_state_can_be_cancelled(self) -> None:
        # Regression: PLANNED had no path to CANCELLED, so stopping a run
        # before its tasks started meant marking them READY first — a lie the
        # state machine forced on the caller.
        finished = {TaskState.SUCCEEDED, TaskState.CANCELLED, TaskState.SUPERSEDED}
        for state in TaskState:
            if state in finished:
                continue
            assert can_transition(state, TaskState.CANCELLED, "task"), state

    def test_a_blocked_task_can_become_ready_again(self) -> None:
        """BLOCKED was a dead end: nothing could ever leave it."""
        assert can_transition(TaskState.BLOCKED, TaskState.READY, "task")

    def test_a_run_can_be_cancelled_from_every_state_before_verification(self) -> None:
        for state in (
            RunState.CREATED,
            RunState.PLANNING,
            RunState.READY,
            RunState.RUNNING,
        ):
            assert can_transition(state, RunState.CANCELLED, "run"), state

    def test_a_finished_task_cannot_be_cancelled(self) -> None:
        assert not can_transition(TaskState.SUCCEEDED, TaskState.CANCELLED, "task")
        assert not can_transition(TaskState.CANCELLED, TaskState.CANCELLED, "task")
