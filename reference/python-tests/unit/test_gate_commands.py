"""P07 declared gate checks: the runtime runs them, it does not invent them."""

import sys
from pathlib import Path

import pytest
import yaml

from atlas_flow.verification.commands import (
    GateCommands,
    VerificationConfigError,
    evidence_for,
    run_gate_command,
)
from atlas_flow.verification.gates import GateKind, GateVerdict


def script(root: Path, body: str, name: str = "check.py") -> str:
    """A real command line, quoted the way a project would write one.

    `shlex.split` consumes quotes, so inlining Python with `-c` turns one
    argument into several and the failure looks like a broken gate rather than
    a broken test.
    """
    target = root / name
    target.write_text(body, encoding="utf-8")
    return f"{sys.executable} {target}"


def write_config(root: Path, data: object) -> Path:
    target = root / ".ai" / "orchestration" / "verification.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(data), encoding="utf-8")
    return target


class TestLoading:
    def test_a_project_with_no_file_declares_nothing(self, tmp_path: Path) -> None:
        assert GateCommands.load(tmp_path).declared() == []

    def test_declared_commands_are_read_per_gate(self, tmp_path: Path) -> None:
        write_config(tmp_path, {"gates": {"tests": "pytest", "documentation": "mkdocs"}})

        commands = GateCommands.load(tmp_path)

        assert commands.declared() == [GateKind.DOCUMENTATION, GateKind.TESTS]
        assert commands.for_gate(GateKind.TESTS) == "pytest"
        assert commands.for_gate(GateKind.BUILD) is None

    def test_an_empty_command_is_the_same_as_not_declaring_one(
        self, tmp_path: Path
    ) -> None:
        write_config(tmp_path, {"gates": {"tests": ""}})

        assert GateCommands.load(tmp_path).declared() == []

    def test_an_unknown_gate_name_is_an_error_not_a_silent_skip(
        self, tmp_path: Path
    ) -> None:
        """A typo would otherwise leave a gate quietly unverified forever."""
        write_config(tmp_path, {"gates": {"tset": "pytest"}})

        with pytest.raises(VerificationConfigError, match="is not a gate"):
            GateCommands.load(tmp_path)

    def test_a_malformed_file_is_an_error(self, tmp_path: Path) -> None:
        write_config(tmp_path, {"gates": ["pytest"]})

        with pytest.raises(VerificationConfigError):
            GateCommands.load(tmp_path)


@pytest.mark.asyncio
class TestRunning:
    async def test_a_passing_command_produces_passing_evidence(
        self, tmp_path: Path
    ) -> None:
        outcome = await run_gate_command(
            GateKind.TESTS, script(tmp_path, "print('42_passed')"), tmp_path
        )

        assert outcome.passed
        assert outcome.verdict == GateVerdict.PASSED
        assert "42_passed" in outcome.detail

    async def test_a_failing_command_produces_failing_evidence_with_its_output(
        self, tmp_path: Path
    ) -> None:
        outcome = await run_gate_command(
            GateKind.TESTS,
            script(tmp_path, "import sys\nprint('3_failed')\nsys.exit(1)\n"),
            tmp_path,
        )

        assert not outcome.passed
        assert "exit 1" in outcome.detail
        assert "3_failed" in outcome.detail

    async def test_a_command_that_does_not_exist_fails_rather_than_raising(
        self, tmp_path: Path
    ) -> None:
        outcome = await run_gate_command(
            GateKind.TESTS, "atlas-flow-no-such-command", tmp_path
        )

        assert not outcome.passed
        assert "could not run" in outcome.detail

    async def test_a_hanging_command_is_killed_and_reported(
        self, tmp_path: Path
    ) -> None:
        outcome = await run_gate_command(
            GateKind.TESTS,
            script(tmp_path, "import time\ntime.sleep(30)\n"),
            tmp_path,
            timeout=0.5,
        )

        assert not outcome.passed
        assert "timed out" in outcome.detail

    async def test_an_empty_command_fails_rather_than_passing_vacuously(
        self, tmp_path: Path
    ) -> None:
        outcome = await run_gate_command(GateKind.TESTS, "   ", tmp_path)

        assert not outcome.passed

    async def test_it_runs_in_the_project_root(self, tmp_path: Path) -> None:
        (tmp_path / "marker.txt").write_text("here", encoding="utf-8")

        outcome = await run_gate_command(
            GateKind.TESTS,
            script(tmp_path, "import pathlib\nprint(pathlib.Path('marker.txt').read_text())\n"),
            tmp_path,
        )

        assert outcome.passed
        assert "here" in outcome.detail

    async def test_a_secret_in_the_output_is_redacted_before_it_becomes_evidence(
        self, tmp_path: Path
    ) -> None:
        outcome = await run_gate_command(
            GateKind.TESTS,
            script(tmp_path, "print('token: ghp_0123456789abcdefghij')"),
            tmp_path,
        )

        assert "ghp_0123456789abcdefghij" not in outcome.detail
        assert "REDACTED" in outcome.detail


def test_evidence_carries_the_command_that_produced_it() -> None:
    """A verdict nobody can reproduce is an opinion."""
    import asyncio

    outcome = asyncio.run(
        run_gate_command(GateKind.TESTS, f"{sys.executable} --version", Path.cwd())
    )
    evidence = evidence_for(outcome, "P07-G01", "run-1")

    assert evidence.goal_id == "P07-G01"
    assert evidence.gate == GateKind.TESTS
    assert evidence.verdict == GateVerdict.PASSED
    assert evidence.kind == "gate_command"
    assert sys.executable in evidence.uri
    assert evidence.run_id == "run-1"
