"""Atlas Harness — meta-harness coordinating coding agent runners (P04)."""

from __future__ import annotations

import asyncio

from atlas_flow.execution.models import Attempt, AttemptState, Task, TaskState
from atlas_flow.execution.persistence import Persistence
from atlas_flow.harness.runner import Runner, RunnerConfig, RunnerResult


class Harness:
    """Meta-harness: selects runners, manages session lifecycle, transcripts."""

    def __init__(self, persistence: Persistence) -> None:
        self.db = persistence
        self._runners: dict[str, Runner] = {}
        self._active_tasks: dict[str, asyncio.Task[RunnerResult]] = {}

    def register(self, runner: Runner) -> None:
        self._runners[runner.name] = runner

    def resolve(self, name: str) -> Runner | None:
        return self._runners.get(name)

    async def execute(
        self,
        runner_name: str,
        task: Task,
        prompt: str,
        config: RunnerConfig | None = None,
    ) -> RunnerResult:
        runner = self.resolve(runner_name)
        if runner is None:
            raise ValueError(f"Unknown runner: {runner_name}")

        config = config or RunnerConfig(model="default")

        attempt = Attempt(
            task_id=task.id,
            run_id=task.run_id,
            runner=runner_name,
            model_id=config.model,
            state=AttemptState.STARTING,
        )

        task.state = TaskState.RUNNING
        await self.db.save_task(task)

        try:
            result = await runner.run(task.id, prompt, config)
            attempt.state = AttemptState.COMPLETED if result.success else AttemptState.FAILED
            if result.error:
                attempt.error_msg = result.error
            return result
        except asyncio.CancelledError:
            attempt.state = AttemptState.CANCELLED
            raise
        except Exception as exc:
            attempt.state = AttemptState.FAILED
            attempt.error_msg = str(exc)
            return RunnerResult(
                task_id=task.id,
                success=False,
                error=str(exc),
            )

    async def cancel_task(self, task_id: str) -> bool:
        future = self._active_tasks.get(task_id)
        if future and not future.done():
            future.cancel()
            return True
        return False
