"""P07 Verification engine tests."""

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
async def initialized_db(persistence: Persistence) -> Persistence:
    await persistence.initialize()
    return persistence


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
        task = Task(run_id=run.id, objective="x", state=TaskState.SUCCEEDED)
        await initialized_db.save_task(task)

        passed = await gate_execution_flow(
            gc, run, task, {"tests": "required"},
        )
        assert not passed

        loaded = await initialized_db.load_tasks(run.id)
        assert loaded[0].state == TaskState.FAILED
