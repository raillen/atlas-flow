"""The rule that keeps a Goal honest: DONE requires evidence (P07).

A Goal declares which gates are required. Marking it DONE asserts those gates
passed, so the assertion has to be checked against evidence rather than
trusted. This module is the single place that decides whether a Goal may be
called done, and it is used both at runtime and by the repository validator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from atlas_flow.goals.models import Goal
from atlas_flow.verification.gates import Evidence, GateKind, GateVerdict

DONE = "DONE"

# A declared evidence entry is free text, and the verdict is the first word of
# it. Anything that opens with one of these is a gate reporting that it did not
# pass, and must never be read as covering that gate.
NON_PASSING_VERDICTS = frozenset(
    {"FAILED", "FAIL", "PENDING", "PARTIAL", "BLOCKED", "UNVERIFIED", "SKIPPED"}
)


def declares_failure(value: object) -> bool:
    """True when an evidence entry opens by reporting a non-passing verdict."""
    text = str(value).strip()
    if not text:
        return True
    first = text.split(":", 1)[0].split("—", 1)[0].split("-", 1)[0].split()
    return bool(first) and first[0].upper() in NON_PASSING_VERDICTS


class GoalNotCompletable(Exception):
    """Raised when a Goal is moved to DONE without the evidence it requires."""


@dataclass
class CompletionCheck:
    goal_id: str
    missing: list[GateKind] = field(default_factory=list)
    failed: list[GateKind] = field(default_factory=list)

    @property
    def completable(self) -> bool:
        return not self.missing and not self.failed

    def describe(self) -> str:
        parts = []
        if self.missing:
            parts.append(
                "no passing evidence for required gate(s): "
                + ", ".join(sorted(self.missing))
            )
        if self.failed:
            parts.append(
                "failing evidence on gate(s): " + ", ".join(sorted(self.failed))
            )
        return f"{self.goal_id}: {'; '.join(parts)}" if parts else f"{self.goal_id}: ok"


def required_gates(goal: Goal) -> list[GateKind]:
    return [
        GateKind(name)
        for name, requirement in goal.gates.model_dump().items()
        if requirement == "required"
    ]


def check_completion(goal: Goal, evidence: list[Evidence]) -> CompletionCheck:
    """Compare a Goal's required gates against the evidence attached to it."""
    check = CompletionCheck(goal_id=goal.id)
    relevant = [e for e in evidence if e.goal_id == goal.id]

    for gate in required_gates(goal):
        for_gate = [e for e in relevant if e.gate == gate]
        if any(e.verdict == GateVerdict.FAILED for e in for_gate):
            check.failed.append(gate)
        elif not any(e.verdict == GateVerdict.PASSED for e in for_gate):
            check.missing.append(gate)
    return check


def assert_goal_completable(goal: Goal, evidence: list[Evidence]) -> None:
    check = check_completion(goal, evidence)
    if not check.completable:
        raise GoalNotCompletable(check.describe())


def goal_file_path(root: Path, goal: Goal) -> Path:
    return root / ".ai" / "goals" / goal.phase / f"{goal.id}.yaml"


def complete_goal(root: Path, goal: Goal, evidence: list[Evidence]) -> Path:
    """Move a Goal to DONE in Git, attaching the evidence that justifies it.

    Refuses when the evidence does not cover every required gate. Git stays the
    canonical authority for Goal state (ADR-009), so completion is a commit to
    the Goal file rather than a row in the operational database.
    """
    assert_goal_completable(goal, evidence)

    path = goal_file_path(root, goal)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GoalNotCompletable(f"{goal.id}: malformed Goal file at {path}")

    declared = list(data.get("evidence") or [])
    for gate in required_gates(goal):
        passing = [
            item
            for item in evidence
            if item.goal_id == goal.id
            and item.gate == gate
            and item.verdict == GateVerdict.PASSED
        ]
        summary = "; ".join(filter(None, (item.uri or item.kind for item in passing)))
        declared.append({str(gate): summary or f"{len(passing)} passing evidence item(s)"})

    data["evidence"] = declared
    data["state"] = DONE
    history = list(data.get("history") or [])
    history.append(
        f"{_today()}: moved to DONE with evidence for "
        f"{', '.join(sorted(str(g) for g in required_gates(goal)))}."
    )
    data["history"] = history

    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88),
        encoding="utf-8",
    )
    return path


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def check_declared_evidence(goal: dict[str, object]) -> CompletionCheck:
    """Validate the evidence a Goal file declares, without a database.

    The repository validator reads Goal YAML directly. An evidence entry is a
    mapping whose keys name the gates it covers, for example:

        evidence:
          - build: "ruff, mypy and tsc clean"
          - tests: "121 pytest, 5 vitest"

    An entry that opens with a non-passing verdict is evidence that the gate
    did *not* pass, and is reported as failing rather than as covering it.
    Counting `review: "FAILED — the reviewer rejected this"` as a satisfied
    review gate is exactly the hole this check exists to close.
    """
    goal_id = str(goal.get("id", "<unknown>"))
    check = CompletionCheck(goal_id=goal_id)

    gates = goal.get("gates")
    required = (
        [name for name, value in gates.items() if value == "required"]
        if isinstance(gates, dict)
        else []
    )

    passing: set[str] = set()
    failing: set[str] = set()
    raw_evidence = goal.get("evidence")
    if isinstance(raw_evidence, list):
        for entry in raw_evidence:
            if not isinstance(entry, dict):
                continue
            for key, value in entry.items():
                if not value:
                    continue
                (failing if declares_failure(value) else passing).add(str(key))

    for name in required:
        if name in failing:
            check.failed.append(GateKind(name))
        elif name not in passing:
            check.missing.append(GateKind(name))
    return check
