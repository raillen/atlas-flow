"""Running the checks a project declares for its own gates (P07).

A Goal says which gates it requires. Until now only `build` ever got evidence,
produced as a side effect of a runner succeeding, so a Goal executed by Atlas
Flow could never become completable on its own — somebody had to attach the
rest by hand. The planning and execution halves of the product worked and the
verification half did not close.

The runtime cannot guess how a project runs its tests, and guessing wrong is
worse than not knowing: a command that fails for the wrong reason is recorded
as failing evidence. So the project declares them, in
`.ai/orchestration/verification.yaml`:

    gates:
      tests: "uv run --project backend pytest"
      documentation: "python scripts/validate_docs.py"

A gate with no command declared records nothing and stays PENDING. That is the
honest outcome — nobody checked — and it is distinguishable from a gate that
was checked and failed.
"""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from atlas_flow.security.guard import SecurityGuard
from atlas_flow.verification.gates import Evidence, GateKind, GateVerdict

CONFIG_FILE = "verification.yaml"
DEFAULT_TIMEOUT = 900.0

# How much of a command's output is kept as evidence. Enough to see what
# failed; not so much that the Goal file becomes a log.
OUTPUT_LIMIT = 600


class VerificationConfigError(Exception):
    """Raised when the declared gate commands cannot be understood."""


@dataclass
class GateCommands:
    """What a project says it runs to satisfy each gate."""

    commands: dict[GateKind, str] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> GateCommands:
        path = root / ".ai" / "orchestration" / CONFIG_FILE
        if not path.is_file():
            return cls()

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise VerificationConfigError(f"{path} must contain a mapping")

        declared = raw.get("gates") or {}
        if not isinstance(declared, dict):
            raise VerificationConfigError(f"{path}: 'gates' must be a mapping")

        commands: dict[GateKind, str] = {}
        for name, command in declared.items():
            try:
                gate = GateKind(str(name))
            except ValueError as exc:
                known = ", ".join(sorted(GateKind))
                raise VerificationConfigError(
                    f"{path}: '{name}' is not a gate. Known gates: {known}"
                ) from exc
            if command:
                commands[gate] = str(command)
        return cls(commands=commands)

    def for_gate(self, gate: GateKind) -> str | None:
        return self.commands.get(gate)

    def declared(self) -> list[GateKind]:
        return sorted(self.commands, key=str)


@dataclass
class GateOutcome:
    gate: GateKind
    verdict: GateVerdict
    command: str
    detail: str

    @property
    def passed(self) -> bool:
        return self.verdict == GateVerdict.PASSED


async def run_gate_command(
    gate: GateKind, command: str, cwd: Path, timeout: float = DEFAULT_TIMEOUT
) -> GateOutcome:
    """Run one declared check and turn its exit code into a verdict.

    Executed as argv, never through a shell: a gate command comes from the
    project's own configuration, but running it through a shell would make
    every character in it meaningful and the failure modes impossible to
    reason about.
    """
    argv = shlex.split(command)
    if not argv:
        return GateOutcome(
            gate, GateVerdict.FAILED, command, "the declared command is empty"
        )

    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except (FileNotFoundError, PermissionError) as exc:
        return GateOutcome(gate, GateVerdict.FAILED, command, f"could not run: {exc}")

    try:
        raw, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        return GateOutcome(
            gate, GateVerdict.FAILED, command, f"timed out after {timeout:g}s"
        )

    output = SecurityGuard.redact_secrets(raw.decode("utf-8", errors="replace")).strip()
    tail = output[-OUTPUT_LIMIT:] if output else "(no output)"
    if process.returncode == 0:
        return GateOutcome(gate, GateVerdict.PASSED, command, tail)
    return GateOutcome(
        gate, GateVerdict.FAILED, command, f"exit {process.returncode}: {tail}"
    )


def evidence_for(outcome: GateOutcome, goal_id: str, run_id: str) -> Evidence:
    return Evidence.new(
        goal_id=goal_id,
        gate=outcome.gate,
        kind="gate_command",
        verdict=outcome.verdict,
        uri=f"{outcome.command} — {outcome.detail}"[:1000],
        run_id=run_id,
    )
