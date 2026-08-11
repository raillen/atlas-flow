"""Attaching evidence to a Goal: it records claims, it does not invent them."""

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "attach_evidence", ROOT / "scripts" / "attach_evidence.py"
)
assert _spec is not None and _spec.loader is not None
attach_evidence = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(attach_evidence)


GOAL = {
    "id": "T01-G01",
    "phase": "T01",
    "title": "A goal",
    "state": "ACTIVE",
    "objective": "Do a thing",
    "acceptance": ["It works"],
    "gates": {
        "build": "required",
        "tests": "required",
        "review": "required",
        "documentation": "optional",
    },
    "evidence": [],
    "history": [],
}


@pytest.fixture
def goal_file(tmp_path: Path) -> Path:
    path = tmp_path / "T01-G01.yaml"
    path.write_text(yaml.safe_dump(GOAL, sort_keys=False), encoding="utf-8")
    return path


def test_evidence_records_its_reference_and_summary(goal_file: Path) -> None:
    data = attach_evidence.attach(
        goal_file, "review", "PASSED", "docs/reviews/r1.md", "3 findings, addressed"
    )

    assert data["evidence"] == [
        {"review": "3 findings, addressed — docs/reviews/r1.md"}
    ]
    assert "review gate PASSED" in data["history"][-1]


def test_a_failing_verdict_is_recorded_as_failing(goal_file: Path) -> None:
    """A gate that did not pass must not read like one that did."""
    data = attach_evidence.attach(
        goal_file, "review", "FAILED", "docs/reviews/r1.md", "2 blocking findings"
    )

    assert data["evidence"][0]["review"].startswith("FAILED: ")


def test_re_attaching_a_gate_replaces_the_earlier_claim(goal_file: Path) -> None:
    """Two answers for one gate is a disagreement, not more evidence."""
    first = attach_evidence.attach(goal_file, "review", "FAILED", "r1", "rejected")
    attach_evidence.write(goal_file, first)

    second = attach_evidence.attach(goal_file, "review", "PASSED", "r2", "fixed")

    reviews = [item for item in second["evidence"] if "review" in item]
    assert len(reviews) == 1
    assert reviews[0]["review"] == "fixed — r2"
    # The rejection is still in the history: replacing the claim does not
    # erase that it was once rejected.
    assert any("FAILED" in line for line in second["history"])


def test_completion_is_refused_until_every_required_gate_is_covered(
    goal_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(attach_evidence, "find_goal", lambda _: goal_file)
    monkeypatch.setattr(
        "sys.argv",
        ["attach_evidence.py", "T01-G01", "review", "--reference", "r1", "--complete"],
    )

    assert attach_evidence.main() == 1
    assert "no passing evidence" in capsys.readouterr().err
    assert yaml.safe_load(goal_file.read_text())["state"] == "ACTIVE"


def test_completion_succeeds_once_the_required_gates_are_covered(
    goal_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(attach_evidence, "find_goal", lambda _: goal_file)

    for gate in ("build", "tests"):
        attach_evidence.write(
            goal_file, attach_evidence.attach(goal_file, gate, "PASSED", "ci", "green")
        )

    monkeypatch.setattr(
        "sys.argv",
        ["attach_evidence.py", "T01-G01", "review", "--reference", "r1", "--complete"],
    )
    assert attach_evidence.main() == 0

    written = yaml.safe_load(goal_file.read_text())
    assert written["state"] == "DONE"
    # The optional gate was never required, and was never claimed either.
    assert {key for item in written["evidence"] for key in item} == {
        "build", "tests", "review",
    }


def test_a_failing_gate_cannot_complete_a_goal(
    goal_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(attach_evidence, "find_goal", lambda _: goal_file)
    for gate in ("build", "tests"):
        attach_evidence.write(
            goal_file, attach_evidence.attach(goal_file, gate, "PASSED", "ci", "green")
        )

    monkeypatch.setattr(
        "sys.argv",
        ["attach_evidence.py", "T01-G01", "review", "--reference", "r1",
         "--verdict", "FAILED", "--complete"],
    )

    assert attach_evidence.main() == 1
    # The refusal now comes from the evidence check rather than from this
    # script's own guard: an entry opening with a failing verdict no longer
    # counts as covering its gate at all.
    assert "failing evidence on gate(s): review" in capsys.readouterr().err
    assert yaml.safe_load(goal_file.read_text())["state"] == "ACTIVE"
