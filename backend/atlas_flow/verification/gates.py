"""Verification engine — gate execution, evidence, repair path (P07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from atlas_flow.execution.models import DomainEvent, EventType, Run, Task, TaskState
from atlas_flow.execution.persistence import Persistence


class GateKind(StrEnum):
    BUILD = "build"
    TESTS = "tests"
    REVIEW = "review"
    DOCUMENTATION = "documentation"


class GateVerdict(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING = "PENDING"


@dataclass
class Evidence:
    id: str
    goal_id: str
    gate: GateKind
    kind: str  # e.g., "ci_log", "test_output", "review_comment"
    uri: str = ""
    digest: str = ""
    attached_at: str = ""
    verdict: GateVerdict = GateVerdict.PENDING


@dataclass
class GateResult:
    gate: GateKind
    verdict: GateVerdict
    evidence_ids: list[str] = field(default_factory=list)
    details: str = ""


@dataclass
class RepairAction:
    task_id: str
    reason: str
    repair_scope: list[str] = field(default_factory=list)


class VerificationError(Exception):
    """Raised when gate execution or evidence validation fails."""


class GateCoordinator:
    """Executes gates and manages evidence against a Goal's acceptance criteria."""

    def __init__(self, persistence: Persistence) -> None:
        self.db = persistence
        self._evidence: dict[str, Evidence] = {}
        self._repairs: list[RepairAction] = []

    def attach_evidence(self, evidence: Evidence) -> None:
        self._evidence[evidence.id] = evidence

    def evaluate_gate(self, gate: GateKind) -> GateResult:
        relevant = [e for e in self._evidence.values() if e.gate == gate]
        passed = [e for e in relevant if e.verdict == GateVerdict.PASSED]
        failed = [e for e in relevant if e.verdict == GateVerdict.FAILED]

        if failed:
            return GateResult(
                gate=gate,
                verdict=GateVerdict.FAILED,
                evidence_ids=[e.id for e in failed],
                details=f"Gate {gate}: {len(failed)} evidence items FAILED",
            )
        if not passed:
            return GateResult(
                gate=gate,
                verdict=GateVerdict.PENDING,
                evidence_ids=[],
                details=f"Gate {gate}: no evidence attached",
            )
        return GateResult(
            gate=gate,
            verdict=GateVerdict.PASSED,
            evidence_ids=[e.id for e in passed],
        )

    def evaluate_all(
        self, required_gates: dict[str, str]
    ) -> dict[GateKind, GateResult]:
        results: dict[GateKind, GateResult] = {}
        for gate_str, requirement in required_gates.items():
            if requirement != "required":
                continue
            gate = GateKind(gate_str)
            results[gate] = self.evaluate_gate(gate)
        return results

    def all_passed(self, required_gates: dict[str, str]) -> bool:
        results = self.evaluate_all(required_gates)
        return all(
            r.verdict == GateVerdict.PASSED
            for r in results.values()
            if r.gate in (GateKind.BUILD, GateKind.TESTS)
        )

    def propose_repair(self, task_id: str, reason: str, scope: list[str]) -> RepairAction:
        repair = RepairAction(task_id=task_id, reason=reason, repair_scope=scope)
        self._repairs.append(repair)
        return repair

    def repair_is_distinct_from_amendment(self, repair: RepairAction) -> bool:
        return repair.task_id != "" and len(repair.repair_scope) > 0


async def gate_execution_flow(
    coordinator: GateCoordinator,
    run: Run,
    task: Task,
    gates: dict[str, str],
) -> bool:
    """Execute gates for a completed task within a run."""
    results = coordinator.evaluate_all(gates)
    all_ok = all(r.verdict == GateVerdict.PASSED for r in results.values())

    for gate, result in results.items():
        evt_type = (
            EventType.GATE_PASSED
            if result.verdict == GateVerdict.PASSED
            else EventType.GATE_FAILED
        )
        await coordinator.db.save_event(
            DomainEvent(
                project_id=run.project_id,
                run_id=run.id,
                type=evt_type,
                payload={
                    "task_id": task.id,
                    "gate": gate,
                    "verdict": result.verdict,
                },
            )
        )

    if not all_ok:
        task.state = TaskState.FAILED
        await coordinator.db.save_task(task)

    return all_ok
