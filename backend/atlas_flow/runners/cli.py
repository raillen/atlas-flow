"""CLI Runner — Command Code headless execution (GAP-05)."""

from __future__ import annotations

import asyncio

from atlas_flow.harness.runner import Runner, RunnerCapability, RunnerConfig, RunnerResult


class CliRunner(Runner):
    """Runner that invokes Command Code in headless mode.

    Uses `cmd --print <prompt> --max-turns <N> --model <id>` per the doc
    at docs/03-implementation/COMMAND_CODE_INTEGRATION.md.
    """

    def __init__(self, name: str = "cmd") -> None:
        super().__init__(name, [
            RunnerCapability.TRANSCRIPT,
            RunnerCapability.RESULT_CAPTURE,
            RunnerCapability.CANCELLATION,
        ])

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        args = [
            "cmd", "--print", prompt,
            "--max-turns", str(config.max_turns),
        ]
        if config.model and config.model != "default":
            args.extend(["--model", config.model])
        args.extend(config.extra_args)

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=config.timeout_seconds,
            )
        except TimeoutError:
            return RunnerResult(
                task_id=task_id,
                success=False,
                error=f"Command Code timed out after {config.timeout_seconds}s",
            )

        output = stdout.decode("utf-8", errors="replace")
        error_output = stderr.decode("utf-8", errors="replace")

        success = proc.returncode == 0
        return RunnerResult(
            task_id=task_id,
            success=success,
            output=output[:8000],
            error=error_output[:2000],
            transcript=output[:8000],
        )

    async def cancel(self, task_id: str) -> bool:
        # CLI runner cancellation is process-level
        return True
