"""P03 Execution runtime tests."""

import pytest

from atlas_flow.execution.models import (
    DomainEvent,
    EventType,
    Run,
    RunState,
    Task,
    TaskState,
    can_transition,
)
from atlas_flow.execution.persistence import Persistence
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
    async def test_initialize_creates_tables(self) -> None:
        db = Persistence(":memory:")
        await db.initialize()
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

    async def test_event_append_only_ordering(self) -> None:
        db = Persistence(":memory:")
        await db.initialize()
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

    async def test_save_load_tasks(self) -> None:
        db = Persistence(":memory:")
        await db.initialize()
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
    async def test_run_lifecycle(self) -> None:
        db = Persistence(":memory:")
        await db.initialize()
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
        await sched.schedule_tasks(run, tasks)

        ready = await sched.ready_tasks(run.id)
        assert len(ready) == 2

        run = await sched.advance_run(run, RunState.RUNNING)
        t1 = await sched.mark_task_ready(ready[0])
        await sched.start_task(t1)
        await sched.complete_task(t1)
        t2 = await sched.mark_task_ready(ready[1])
        await sched.start_task(t2)
        await sched.complete_task(t2)

        done = await sched.evaluate_run_completion(run)
        assert done is True

    async def test_recovery_resets_orhpans(self) -> None:
        db = Persistence(":memory:")
        await db.initialize()
        run = Run(
            project_id="atlas-flow",
            goal_id="G1",
            goal_revision="abc",
            state=RunState.RUNNING,
        )
        await db.save_run(run)
        recovered = await recover_run(db, run.id)
        assert recovered is not None
        assert recovered.state == RunState.CREATED
