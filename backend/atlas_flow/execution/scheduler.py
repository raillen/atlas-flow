"""Run scheduler and state machine (P03)."""

from __future__ import annotations

import asyncio

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


class Scheduler:
    """Minimal dependency-aware scheduler with transactional state changes."""

    def __init__(self, persistence: Persistence) -> None:
        self.db = persistence
        self._lock = asyncio.Lock()

    async def start_run(self, run: Run) -> Run:
        if not can_transition(run.state, RunState.PLANNING, "run"):
            raise ValueError(
                f"Cannot transition run {run.id} from {run.state} to PLANNING"
            )
        run.state = RunState.PLANNING
        await self.db.save_run(run)
        await self._emit(run, EventType.RUN_STARTED)
        return run

    async def advance_run(self, run: Run, to_state: RunState) -> Run:
        if not can_transition(run.state, to_state, "run"):
            raise ValueError(
                f"Invalid run transition: {run.state} -> {to_state}"
            )
        run.state = to_state
        await self.db.save_run(run)
        await self._emit(
            run, EventType.STATE_CHANGE, {"previous": run.state, "next": to_state}
        )
        if to_state == RunState.COMPLETED:
            await self._emit(run, EventType.RUN_COMPLETED)
        elif to_state == RunState.FAILED:
            await self._emit(run, EventType.RUN_FAILED)
        return run

    async def schedule_tasks(self, run: Run, tasks: list[Task]) -> list[Task]:
        async with self._lock:
            for t in tasks:
                await self.db.save_task(t)
            run.state = RunState.READY
            await self.db.save_run(run)
        return tasks

    async def ready_tasks(self, run_id: str) -> list[Task]:
        tasks = await self.db.load_tasks(run_id)
        return [
            t for t in tasks
            if t.state == TaskState.PLANNED and t.dependencies == []
        ]

    async def mark_task_ready(self, task: Task) -> Task:
        if not can_transition(task.state, TaskState.READY, "task"):
            raise ValueError(
                f"Cannot transition task {task.id} from {task.state} to READY"
            )
        task.state = TaskState.READY
        await self.db.save_task(task)
        return task

    async def start_task(self, task: Task) -> Task:
        if not can_transition(task.state, TaskState.RUNNING, "task"):
            raise ValueError(
                f"Cannot transition task {task.id} from {task.state} to RUNNING"
            )
        task.state = TaskState.RUNNING
        await self.db.save_task(task)
        return task

    async def complete_task(self, task: Task) -> Task:
        if not can_transition(task.state, TaskState.SUCCEEDED, "task"):
            raise ValueError(
                f"Cannot transition task {task.id} from {task.state} to SUCCEEDED"
            )
        task.state = TaskState.SUCCEEDED
        await self.db.save_task(task)
        await self.db.save_event(
            DomainEvent(
                project_id="atlas-flow",
                run_id=task.run_id,
                type=EventType.TASK_SUCCEEDED,
                payload={"task_id": task.id, "objective": task.objective},
            )
        )
        return task

    async def evaluate_run_completion(self, run: Run) -> bool:
        tasks = await self.db.load_tasks(run.id)
        if not tasks:
            return False
        all_done = all(
            t.state in (TaskState.SUCCEEDED, TaskState.CANCELLED, TaskState.SUPERSEDED)
            for t in tasks
        )
        any_failed = any(t.state == TaskState.FAILED for t in tasks)
        if all_done and not any_failed:
            await self.advance_run(run, RunState.VERIFYING)
            return True
        if any_failed:
            await self.advance_run(run, RunState.FAILED)
            return False
        return False

    async def _emit(
        self, run: Run, event_type: EventType, extra_payload: dict[str, object] | None = None
    ) -> None:
        payload: dict[str, object] = {
            "run_id": run.id,
            "goal_id": run.goal_id,
            "state": run.state,
        }
        if extra_payload:
            payload.update(extra_payload)
        await self.db.save_event(
            DomainEvent(
                project_id=run.project_id,
                run_id=run.id,
                type=event_type,
                payload=payload,
            )
        )


async def recover_run(persistence: Persistence, run_id: str) -> Run | None:
    """Idempotent recovery: load durable state, re-attach if possible."""
    run = await persistence.load_run(run_id)
    if run is None:
        return None
    events = await persistence.load_events(run_id)
    if not events and run.state in (RunState.RUNNING, RunState.PLANNING):
        run.state = RunState.CREATED
        await persistence.save_run(run)
    return run
