"""P07 Verification engine tests."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from atlas_flow.execution.models import Run, RunState, Task, TaskState
from atlas_flow.execution.persistence import Persistence
from atlas_flow.verification.gates import (
    Evidence,
    GateCoordinator,
    GateKind,
    GateVerdict,
    RepairAction,
    gate_execution_flow,
)


@pytest.fixture
def persistence() -> Persistence:
    return Persistence(":memory:")


@pytest_asyncio.fixture
async def initialized_db(persistence: Persistence) -> AsyncIterator[Persistence]:
    await persistence.initialize()
    try:
        yield persistence
    finally:
        await persistence.close()


class TestGateCoordinator:
    def test_all_pending_when_no_evidence(self) -> None:
        gc = GateCoordinator(Persistence(":memory:"))
        result = gc.evaluate_gate(GateKind.BUILD)
        assert result.verdict == GateVerdict.PENDING

    def test_pass_with_evidence(self) -> None:
        gc = GateCoordinator(Persistence(":memory:"))
        gc.attach_evidence(Evidence(
            id="e1", goal_id="G1", gate=GateKind.BUILD,
            kind="ci_log", verdict=GateVerdict.PASSED,
        ))
        result = gc.evaluate_gate(GateKind.BUILD)
        assert result.verdict == GateVerdict.PASSED

    def test_fail_on_any_failed_evidence(self) -> None:
        gc = GateCoordinator(Persistence(":memory:"))
        gc.attach_evidence(Evidence(
            id="e1", goal_id="G1", gate=GateKind.TESTS,
            kind="test_output", verdict=GateVerdict.PASSED,
        ))
        gc.attach_evidence(Evidence(
            id="e2", goal_id="G1", gate=GateKind.TESTS,
            kind="test_output", verdict=GateVerdict.FAILED,
        ))
        result = gc.evaluate_gate(GateKind.TESTS)
        assert result.verdict == GateVerdict.FAILED

    def test_evaluate_all_required(self) -> None:
        gc = GateCoordinator(Persistence(":memory:"))
        gc.attach_evidence(Evidence(
            id="e1", goal_id="G1", gate=GateKind.BUILD,
            kind="ci", verdict=GateVerdict.PASSED,
        ))
        gc.attach_evidence(Evidence(
            id="e2", goal_id="G1", gate=GateKind.TESTS,
            kind="test", verdict=GateVerdict.PASSED,
        ))
        results = gc.evaluate_all({"build": "required", "tests": "required"})
        assert all(r.verdict == GateVerdict.PASSED for r in results.values())

    def test_all_passed_shortcut(self) -> None:
        gc = GateCoordinator(Persistence(":memory:"))
        gc.attach_evidence(Evidence(
            id="e1", goal_id="G1", gate=GateKind.BUILD,
            kind="ci", verdict=GateVerdict.PASSED,
        ))
        gc.attach_evidence(Evidence(
            id="e2", goal_id="G1", gate=GateKind.TESTS,
            kind="test", verdict=GateVerdict.PASSED,
        ))
        assert gc.all_passed({"build": "required", "tests": "required"})


class TestRepair:
    def test_repair_distinct_from_amendment(self) -> None:
        gc = GateCoordinator(Persistence(":memory:"))
        repair = gc.propose_repair("task-1", "fix lint", ["backend/lint"])
        assert gc.repair_is_distinct_from_amendment(repair)
        assert repair.reason == "fix lint"

    def test_empty_repair_not_valid(self) -> None:
        gc = GateCoordinator(Persistence(":memory:"))
        repair = RepairAction(task_id="", reason="", repair_scope=[])
        assert not gc.repair_is_distinct_from_amendment(repair)


@pytest.mark.asyncio
class TestGateExecutionFlow:
    async def test_gate_flow_emits_events(self, initialized_db: Persistence) -> None:
        gc = GateCoordinator(initialized_db)
        gc.attach_evidence(Evidence(
            id="e1", goal_id="G1", gate=GateKind.BUILD,
            kind="ci", verdict=GateVerdict.PASSED,
        ))
        gc.attach_evidence(Evidence(
            id="e2", goal_id="G1", gate=GateKind.TESTS,
            kind="test", verdict=GateVerdict.PASSED,
        ))

        run = Run(
            project_id="atlas-flow",
            goal_id="G1",
            goal_revision="abc",
            state=RunState.RUNNING,
        )
        await initialized_db.save_run(run)

        task = Task(run_id=run.id, objective="x", state=TaskState.SUCCEEDED)
        await initialized_db.save_task(task)

        passed = await gate_execution_flow(
            gc, run, task,
            {"build": "required", "tests": "required"},
        )
        assert passed

    async def test_gate_flow_fails_task_on_failure(self, initialized_db: Persistence) -> None:
        gc = GateCoordinator(initialized_db)
        gc.attach_evidence(Evidence(
            id="e1", goal_id="G1", gate=GateKind.TESTS,
            kind="test", verdict=GateVerdict.FAILED,
        ))

        run = Run(
            project_id="atlas-flow",
            goal_id="G1",
            goal_revision="abc",
            state=RunState.RUNNING,
        )
        await initialized_db.save_run(run)
        # Gates run against a task that is still RUNNING: that is the point at
        # which failing them can still stop it from being called done.
        task = Task(run_id=run.id, objective="x", state=TaskState.RUNNING)
        await initialized_db.save_task(task)

        passed = await gate_execution_flow(
            gc, run, task, {"tests": "required"},
        )
        assert not passed

        loaded = await initialized_db.load_tasks(run.id)
        assert loaded[0].state == TaskState.FAILED

    async def test_gate_flow_does_not_reopen_a_finished_task(
        self, initialized_db: Persistence
    ) -> None:
        """A succeeded task is not flipped to failed behind the state machine.

        Re-litigating a finished task is the repair path's job, and a repair is
        an explicit, authorized action rather than a side effect of evaluation.
        """
        gc = GateCoordinator(initialized_db)
        gc.attach_evidence(Evidence(
            id="e1", goal_id="G1", gate=GateKind.TESTS,
            kind="test", verdict=GateVerdict.FAILED,
        ))

        run = Run(
            project_id="atlas-flow", goal_id="G1", goal_revision="abc",
            state=RunState.RUNNING,
        )
        await initialized_db.save_run(run)
        task = Task(run_id=run.id, objective="x", state=TaskState.SUCCEEDED)
        await initialized_db.save_task(task)

        assert not await gate_execution_flow(gc, run, task, {"tests": "required"})

        loaded = await initialized_db.load_tasks(run.id)
        assert loaded[0].state == TaskState.SUCCEEDED

    async def test_required_review_gate_is_not_exempt(
        self, initialized_db: Persistence
    ) -> None:
        """Regression: all_passed used to ignore review and documentation.

        That let a Goal declare a gate required and still be reported as fully
        passing without it, which silently weakens the Goal's acceptance.
        """
        gc = GateCoordinator(initialized_db)
        for gate in (GateKind.BUILD, GateKind.TESTS):
            gc.attach_evidence(Evidence(
                id=f"e-{gate}", goal_id="G1", gate=gate,
                kind="ci", verdict=GateVerdict.PASSED,
            ))

        required = {
            "build": "required",
            "tests": "required",
            "review": "required",
            "documentation": "required",
        }
        assert not gc.all_passed(required)
        assert gc.pending_gates(required) == [GateKind.REVIEW, GateKind.DOCUMENTATION]

        for gate in (GateKind.REVIEW, GateKind.DOCUMENTATION):
            gc.attach_evidence(Evidence(
                id=f"e-{gate}", goal_id="G1", gate=gate,
                kind="review", verdict=GateVerdict.PASSED,
            ))
        assert gc.all_passed(required)

    async def test_evidence_survives_a_new_coordinator(
        self, initialized_db: Persistence
    ) -> None:
        first = GateCoordinator(initialized_db)
        await first.record_evidence(
            Evidence.new(
                goal_id="G1",
                gate=GateKind.TESTS,
                kind="pytest",
                verdict=GateVerdict.PASSED,
                uri="ci://run/42",
            )
        )

        second = GateCoordinator(initialized_db)
        assert second.evaluate_gate(GateKind.TESTS).verdict == GateVerdict.PENDING

        loaded = await second.load_evidence("G1")
        assert len(loaded) == 1
        assert loaded[0].uri == "ci://run/42"
        assert second.evaluate_gate(GateKind.TESTS).verdict == GateVerdict.PASSED
