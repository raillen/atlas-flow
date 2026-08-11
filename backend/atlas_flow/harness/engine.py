"""Atlas Harness — meta-harness coordinating coding agent runners (P04)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from atlas_flow.execution.models import (
    UNKNOWN_PROJECT,
    Attempt,
    AttemptState,
    DomainEvent,
    EventType,
    Task,
    TaskState,
)
from atlas_flow.execution.persistence import Persistence
from atlas_flow.harness.runner import Runner, RunnerCapability, RunnerConfig, RunnerResult


class CapabilityError(Exception):
    """Raised when a runner cannot satisfy the capabilities a task requires."""


class Harness:
    """Meta-harness: selects runners, manages session lifecycle, transcripts.

    Every attempt is persisted through its whole lifecycle. The scorecard and
    the Build screen both read attempts back from the database, so an attempt
    that only exists in memory is an attempt that never happened.
    """

    def __init__(
        self, persistence: Persistence, project_id: str = UNKNOWN_PROJECT
    ) -> None:
        self.db = persistence
        self.project_id = project_id
        self._runners: dict[str, Runner] = {}
        self._active_tasks: dict[str, asyncio.Task[RunnerResult]] = {}

    def register(self, runner: Runner) -> None:
        self._runners[runner.name] = runner

    def resolve(self, name: str) -> Runner | None:
        return self._runners.get(name)

    def runners(self) -> list[str]:
        return sorted(self._runners)

    def select_runner(self, required: list[RunnerCapability]) -> Runner:
        """Pick a registered runner that satisfies every required capability."""
        for name in sorted(self._runners):
            runner = self._runners[name]
            if len(runner.negotiate(required)) == len(set(required)):
                return runner
        wanted = ", ".join(sorted(set(required))) or "none"
        raise CapabilityError(f"No registered runner provides all of: {wanted}")

    async def execute(
        self,
        runner_name: str,
        task: Task,
        prompt: str,
        config: RunnerConfig | None = None,
        required: list[RunnerCapability] | None = None,
    ) -> tuple[RunnerResult, Attempt]:
        runner = self.resolve(runner_name)
        if runner is None:
            raise ValueError(f"Unknown runner: {runner_name}")

        if required:
            missing = set(required) - set(runner.negotiate(required))
            if missing:
                raise CapabilityError(
                    f"Runner {runner_name} is missing capabilities: "
                    f"{', '.join(sorted(missing))}"
                )

        config = config or RunnerConfig(model="default")

        attempt = Attempt(
            task_id=task.id,
            run_id=task.run_id,
            runner=runner_name,
            model_id=config.model,
        )
        await self.db.save_attempt(attempt)

        attempt = await self.db.record_attempt_transition(
            attempt,
            AttemptState.STARTING,
            self._attempt_event(attempt, EventType.ATTEMPT_STARTED),
        )
        attempt = attempt.model_copy(update={"started_at": _now_iso()})
        attempt = await self.db.record_attempt_transition(
            attempt,
            AttemptState.RUNNING,
            self._attempt_event(attempt, EventType.STATE_CHANGE),
        )

        if task.state == TaskState.READY:
            task = await self.db.record_task_transition(
                task,
                TaskState.RUNNING,
                self._task_event(task, EventType.STATE_CHANGE),
            )

        try:
            result = await runner.run(task.id, prompt, config)
        except asyncio.CancelledError:
            await self._close_attempt(
                attempt, AttemptState.CANCELLED, EventType.ATTEMPT_FAILED
            )
            raise
        except Exception as exc:
            attempt = await self._close_attempt(
                attempt,
                AttemptState.FAILED,
                EventType.ATTEMPT_FAILED,
                error=str(exc),
            )
            return RunnerResult(task_id=task.id, success=False, error=str(exc)), attempt

        if result.success:
            attempt = await self._close_attempt(
                attempt, AttemptState.COMPLETED, EventType.ATTEMPT_COMPLETED
            )
        else:
            attempt = await self._close_attempt(
                attempt,
                AttemptState.FAILED,
                EventType.ATTEMPT_FAILED,
                error=result.error,
            )
        return result, attempt

    async def _close_attempt(
        self,
        attempt: Attempt,
        state: AttemptState,
        event_type: EventType,
        error: str = "",
    ) -> Attempt:
        finished = attempt.model_copy(
            update={"completed_at": _now_iso(), "error_msg": error or None}
        )
        return await self.db.record_attempt_transition(
            finished, state, self._attempt_event(finished, event_type)
        )

    def _attempt_event(self, attempt: Attempt, event_type: EventType) -> DomainEvent:
        return DomainEvent(
            project_id=self.project_id,
            run_id=attempt.run_id,
            type=event_type,
            payload={
                "attempt_id": attempt.id,
                "task_id": attempt.task_id,
                "runner": attempt.runner,
                "model_id": attempt.model_id,
                "previous": str(attempt.state),
            },
        )

    def _task_event(self, task: Task, event_type: EventType) -> DomainEvent:
        return DomainEvent(
            project_id=self.project_id,
            run_id=task.run_id,
            type=event_type,
            payload={"task_id": task.id, "previous": str(task.state)},
        )

    async def cancel_task(self, task_id: str) -> bool:
        future = self._active_tasks.get(task_id)
        if future and not future.done():
            future.cancel()
            return True
        return False


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
