"""Run scheduler and state machine (P03)."""

from __future__ import annotations

import asyncio

from atlas_flow.execution.models import (
    UNKNOWN_PROJECT,
    Attempt,
    AttemptState,
    DomainEvent,
    EventType,
    Run,
    RunState,
    Task,
    TaskState,
)
from atlas_flow.execution.persistence import Persistence


class Scheduler:
    """Dependency-aware scheduler with transactional state changes.

    Every state change is written together with the event that explains it, so
    the event log always accounts for the state that recovery reads back.
    """

    def __init__(
        self, persistence: Persistence, project_id: str = UNKNOWN_PROJECT
    ) -> None:
        self.db = persistence
        # Stamped on every event this scheduler writes. Atlas Flow runs against
        # whatever project it was opened on, so nothing here may assume one.
        self.project_id = project_id
        self._lock = asyncio.Lock()

    async def start_run(self, run: Run) -> Run:
        return await self.db.record_run_transition(
            run,
            RunState.PLANNING,
            _run_event(run, EventType.RUN_STARTED, RunState.PLANNING),
        )

    async def advance_run(self, run: Run, to_state: RunState) -> Run:
        event_type = {
            RunState.COMPLETED: EventType.RUN_COMPLETED,
            RunState.FAILED: EventType.RUN_FAILED,
        }.get(to_state, EventType.STATE_CHANGE)

        return await self.db.record_run_transition(
            run, to_state, _run_event(run, event_type, to_state)
        )

    async def schedule_tasks(self, run: Run, tasks: list[Task]) -> tuple[Run, list[Task]]:
        """Persist a planned task set and move the run to READY."""
        async with self._lock:
            for task in tasks:
                await self.db.save_task(task)
            updated = await self.db.record_run_transition(
                run,
                RunState.READY,
                _run_event(run, EventType.STATE_CHANGE, RunState.READY,
                           {"task_count": len(tasks)}),
            )
        return updated, tasks

    async def ready_tasks(self, run_id: str) -> list[Task]:
        """Tasks whose dependencies have all succeeded."""
        tasks = await self.db.load_tasks(run_id)
        by_id = {task.id: task for task in tasks}
        return [
            task for task in tasks
            if task.state == TaskState.PLANNED and self._dependencies_met(task, by_id)
        ]

    @staticmethod
    def _dependencies_met(task: Task, by_id: dict[str, Task]) -> bool:
        for dependency_id in task.dependencies:
            dependency = by_id.get(dependency_id)
            if dependency is None or dependency.state != TaskState.SUCCEEDED:
                return False
        return True

    async def mark_task_ready(self, task: Task) -> Task:
        return await self.db.record_task_transition(
            task,
            TaskState.READY,
            _task_event(task, EventType.TASK_READY, project_id=self.project_id),
        )

    async def start_task(self, task: Task) -> Task:
        return await self.db.record_task_transition(
            task,
            TaskState.RUNNING,
            _task_event(task, EventType.STATE_CHANGE, project_id=self.project_id),
        )

    async def complete_task(self, task: Task) -> Task:
        return await self.db.record_task_transition(
            task,
            TaskState.SUCCEEDED,
            _task_event(task, EventType.TASK_SUCCEEDED, project_id=self.project_id),
        )

    async def fail_task(self, task: Task, reason: str) -> Task:
        return await self.db.record_task_transition(
            task,
            TaskState.FAILED,
            _task_event(task, EventType.TASK_FAILED, {"reason": reason},
                        project_id=self.project_id),
        )

    async def cancel_task(self, task: Task, reason: str) -> Task:
        """Close a task nobody is going to finish."""
        return await self.db.record_task_transition(
            task,
            TaskState.CANCELLED,
            _task_event(task, EventType.TASK_FAILED, {"reason": reason},
                        project_id=self.project_id),
        )

    async def cancel_run(self, run: Run, reason: str) -> Run:
        """Close a run and everything in it that is still open.

        Tasks that were never started are cancelled rather than failed: a task
        that nobody ran did not fail, and recording it as a failure would make
        the run look like it went wrong when it was stopped on purpose.
        """
        open_states = (
            TaskState.PLANNED,
            TaskState.BLOCKED,
            TaskState.READY,
            TaskState.RUNNING,
        )
        for task in await self.db.load_tasks(run.id):
            if task.state in open_states:
                await self.cancel_task(task, reason)

        reloaded = await self.db.load_run(run.id) or run
        if reloaded.state in (RunState.PLANNING, RunState.READY, RunState.RUNNING):
            return await self.db.record_run_transition(
                reloaded,
                RunState.CANCELLED,
                _run_event(reloaded, EventType.RUN_FAILED, RunState.CANCELLED,
                           {"reason": reason}),
            )
        return reloaded

    async def evaluate_run_completion(self, run: Run) -> bool:
        tasks = await self.db.load_tasks(run.id)
        if not tasks:
            return False
        if any(task.state == TaskState.FAILED for task in tasks):
            await self.advance_run(run, RunState.FAILED)
            return False
        if any(task.state == TaskState.CANCELLED for task in tasks):
            # Stopping on purpose is not the same as failing, and a run whose
            # work was cancelled must not be reported as verifiable.
            await self.advance_run(run, RunState.CANCELLED)
            return False
        terminal = (TaskState.SUCCEEDED, TaskState.CANCELLED, TaskState.SUPERSEDED)
        if all(task.state in terminal for task in tasks):
            await self.advance_run(run, RunState.VERIFYING)
            return True
        return False


def _run_event(
    run: Run,
    event_type: EventType,
    to_state: RunState,
    extra: dict[str, object] | None = None,
) -> DomainEvent:
    payload: dict[str, object] = {
        "run_id": run.id,
        "goal_id": run.goal_id,
        "previous": str(run.state),
        "next": str(to_state),
    }
    if extra:
        payload.update(extra)
    return DomainEvent(
        project_id=run.project_id,
        run_id=run.id,
        type=event_type,
        payload=payload,
    )


def _task_event(
    task: Task,
    event_type: EventType,
    extra: dict[str, object] | None = None,
    project_id: str = UNKNOWN_PROJECT,
) -> DomainEvent:
    payload: dict[str, object] = {
        "task_id": task.id,
        "objective": task.objective,
        "previous": str(task.state),
    }
    if extra:
        payload.update(extra)
    return DomainEvent(
        project_id=project_id,
        run_id=task.run_id,
        type=event_type,
        payload=payload,
    )


class RecoveryReport:
    """What reconciliation changed when a run was reopened after a crash."""

    def __init__(self, run: Run) -> None:
        self.run = run
        self.orphaned_tasks: list[str] = []
        self.orphaned_attempts: list[str] = []

    @property
    def reconciled(self) -> bool:
        return bool(self.orphaned_tasks or self.orphaned_attempts)


async def recover_run(persistence: Persistence, run_id: str) -> RecoveryReport | None:
    """Reconcile a run whose process died mid-flight.

    A task or attempt left in a running state has no live process behind it
    after a restart, so it is closed as failed rather than left to look active
    forever. Failed tasks are retryable, which keeps recovery idempotent:
    running it twice finds nothing left to reconcile.
    """
    run = await persistence.load_run(run_id)
    if run is None:
        return None

    report = RecoveryReport(run)

    for attempt in await persistence.load_attempts(run_id):
        if attempt.state in (AttemptState.STARTING, AttemptState.RUNNING):
            await persistence.record_attempt_transition(
                attempt,
                AttemptState.FAILED,
                _attempt_recovery_event(attempt, run.project_id),
            )
            report.orphaned_attempts.append(attempt.id)

    for task in await persistence.load_tasks(run_id):
        if task.state == TaskState.RUNNING:
            await persistence.record_task_transition(
                task,
                TaskState.FAILED,
                _task_event(
                    task,
                    EventType.TASK_FAILED,
                    {"reason": "interrupted by process restart"},
                    project_id=run.project_id,
                ),
            )
            report.orphaned_tasks.append(task.id)

    if report.orphaned_tasks and run.state == RunState.RUNNING:
        report.run = await persistence.record_run_transition(
            run,
            RunState.BLOCKED,
            _run_event(
                run,
                EventType.STATE_CHANGE,
                RunState.BLOCKED,
                {"reason": "recovered with interrupted tasks"},
            ),
        )

    return report


def _attempt_recovery_event(attempt: Attempt, project_id: str) -> DomainEvent:
    return DomainEvent(
        project_id=project_id,
        run_id=attempt.run_id,
        type=EventType.ATTEMPT_FAILED,
        payload={
            "attempt_id": attempt.id,
            "task_id": attempt.task_id,
            "previous": str(attempt.state),
            "reason": "interrupted by process restart",
        },
    )
