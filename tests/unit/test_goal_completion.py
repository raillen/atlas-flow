"""P07: a Goal cannot be called DONE without the evidence it requires."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from atlas_flow.goals.models import Goal, GoalGates
from atlas_flow.verification.gates import Evidence, GateKind, GateVerdict
from atlas_flow.verification.goal_completion import (
    GoalNotCompletable,
    assert_goal_completable,
    check_completion,
    check_declared_evidence,
    complete_goal,
    required_gates,
)

ROOT = Path(__file__).resolve().parents[2]


def _goal(goal_id: str = "P01-G01", **gate_overrides: str) -> Goal:
    gates = {
        "build": "required",
        "tests": "required",
        "review": "required",
        "documentation": "required",
    }
    gates.update(gate_overrides)
    return Goal(
        id=goal_id,
        phase=goal_id.split("-")[0],
        title="Example",
        state="ACTIVE",
        objective="Do the thing",
        acceptance=["It works"],
        gates=GoalGates(**gates),
    )


def _evidence(goal_id: str, gate: GateKind, verdict: GateVerdict) -> Evidence:
    return Evidence.new(
        goal_id=goal_id, gate=gate, kind="ci", verdict=verdict
    )


class TestCompletionCheck:
    def test_required_gates_reads_the_goal_contract(self) -> None:
        goal = _goal(review="optional")
        assert GateKind.REVIEW not in required_gates(goal)
        assert GateKind.BUILD in required_gates(goal)

    def test_goal_without_evidence_is_not_completable(self) -> None:
        check = check_completion(_goal(), [])
        assert not check.completable
        assert set(check.missing) == {
            GateKind.BUILD, GateKind.TESTS, GateKind.REVIEW, GateKind.DOCUMENTATION
        }

    def test_goal_with_all_passing_evidence_is_completable(self) -> None:
        goal = _goal()
        evidence = [
            _evidence(goal.id, gate, GateVerdict.PASSED) for gate in required_gates(goal)
        ]
        assert check_completion(goal, evidence).completable
        assert_goal_completable(goal, evidence)

    def test_failing_evidence_blocks_completion(self) -> None:
        goal = _goal()
        evidence = [
            _evidence(goal.id, gate, GateVerdict.PASSED) for gate in required_gates(goal)
        ]
        evidence.append(_evidence(goal.id, GateKind.TESTS, GateVerdict.FAILED))

        check = check_completion(goal, evidence)
        assert not check.completable
        assert check.failed == [GateKind.TESTS]

    def test_evidence_from_another_goal_does_not_count(self) -> None:
        goal = _goal("P02-G01")
        borrowed = [
            _evidence("P01-G01", gate, GateVerdict.PASSED) for gate in required_gates(goal)
        ]
        with pytest.raises(GoalNotCompletable, match="P02-G01"):
            assert_goal_completable(goal, borrowed)

    def test_optional_gate_needs_no_evidence(self) -> None:
        goal = _goal(review="optional", documentation="optional")
        evidence = [
            _evidence(goal.id, GateKind.BUILD, GateVerdict.PASSED),
            _evidence(goal.id, GateKind.TESTS, GateVerdict.PASSED),
        ]
        assert check_completion(goal, evidence).completable


class TestCompleteGoal:
    def _write_goal_file(self, root: Path, goal: Goal) -> Path:
        path = root / ".ai" / "goals" / goal.phase / f"{goal.id}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(goal.model_dump(), sort_keys=False), encoding="utf-8"
        )
        return path

    def test_completing_writes_state_and_evidence_to_git(self, tmp_path: Path) -> None:
        goal = _goal()
        self._write_goal_file(tmp_path, goal)
        evidence = [
            _evidence(goal.id, gate, GateVerdict.PASSED) for gate in required_gates(goal)
        ]

        path = complete_goal(tmp_path, goal, evidence)
        written = yaml.safe_load(path.read_text(encoding="utf-8"))

        assert written["state"] == "DONE"
        declared = {key for entry in written["evidence"] for key in entry}
        assert declared == {"build", "tests", "review", "documentation"}
        assert any("moved to DONE" in line for line in written["history"])

        # The file it produces must satisfy the repository validator.
        assert check_declared_evidence(written).completable

    def test_completing_without_evidence_is_refused_and_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        goal = _goal()
        path = self._write_goal_file(tmp_path, goal)
        before = path.read_text(encoding="utf-8")

        with pytest.raises(GoalNotCompletable, match="required gate"):
            complete_goal(tmp_path, goal, [])

        assert path.read_text(encoding="utf-8") == before


class TestDeclaredEvidence:
    def test_declared_evidence_covers_required_gates(self) -> None:
        goal = {
            "id": "P00-G01",
            "gates": {"build": "required", "tests": "required"},
            "evidence": [{"build": "ruff/mypy clean"}, {"tests": "121 pytest"}],
        }
        assert check_declared_evidence(goal).completable

    def test_empty_evidence_is_rejected(self) -> None:
        goal = {
            "id": "P00-G01",
            "gates": {"build": "required", "tests": "required"},
            "evidence": [],
        }
        check = check_declared_evidence(goal)
        assert not check.completable
        assert set(check.missing) == {GateKind.BUILD, GateKind.TESTS}

    def test_evidence_with_an_empty_value_does_not_count(self) -> None:
        goal = {
            "id": "P00-G01",
            "gates": {"build": "required"},
            "evidence": [{"build": ""}],
        }
        assert not check_declared_evidence(goal).completable


class TestValidatorEnforcement:
    def test_validator_rejects_a_goal_marked_done_without_evidence(
        self, tmp_path: Path
    ) -> None:
        """The repository validator, not just the library, must refuse this.

        This is the check that stops a Goal from being marked done by editing
        one word in a YAML file, so it is exercised end to end.
        """
        fake_repo = tmp_path / "repo"
        goal_dir = fake_repo / ".ai" / "goals" / "P00"
        goal_dir.mkdir(parents=True)
        (goal_dir / "P00-G01.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "P00-G01",
                    "phase": "P00",
                    "title": "Fake",
                    "state": "DONE",
                    "objective": "Claim completion",
                    "constraints": [],
                    "acceptance": ["Something"],
                    "gates": {
                        "build": "required",
                        "tests": "required",
                        "review": "required",
                        "documentation": "required",
                    },
                    "dependencies": [],
                    "evidence": [],
                }
            ),
            encoding="utf-8",
        )

        script = (fake_repo / "scripts")
        script.mkdir()
        (script / "validate_goals.py").write_text(
            (ROOT / "scripts" / "validate_goals.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        result = subprocess.run(
            [sys.executable, str(script / "validate_goals.py")],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        assert "state is DONE" in result.stdout
        assert "build" in result.stdout

    def test_real_repository_goals_validate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_goals.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Goal validation: PASS" in result.stdout
