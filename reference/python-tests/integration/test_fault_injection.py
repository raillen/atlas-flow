"""P09 fault injection: what a real run does when things actually go wrong.

These drive the whole execution path with a runner that misbehaves in a
specific way, rather than asserting that a bookkeeping class counts its own
registrations. A fault that never reaches a run proves nothing about recovery.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.execution.faults import FaultInjector, FaultKind, FaultPoint
from atlas_flow.execution.goal_runner import GoalRunner
from atlas_flow.execution.models import (
    Attempt,
    AttemptState,
    DomainEvent,
    EventType,
    Run,
    RunState,
    Task,
    TaskState,
)
from atlas_flow.execution.persistence import Persistence
from atlas_flow.execution.scheduler import recover_run
from atlas_flow.harness.engine import Harness
from atlas_flow.harness.runner import Runner, RunnerCapability, RunnerConfig, RunnerResult
from atlas_flow.planner.dag import Plan, TaskNode
from atlas_flow.planner.worktree import WorktreeManager, run_git
from atlas_flow.verification.gates import GateKind, GateVerdict


class FaultyRunner(Runner):
    """Runner that fails the way a registered fault says it should."""

    def __init__(self, injector: FaultInjector, kind: FaultKind, name: str = "faulty") -> None:
        super().__init__(name, list(RunnerCapability))
        self.injector = injector
        self.kind = kind
        self.calls = 0

    # Task ids are generated inside execute(), so the fault is registered under
    # a scope the runner knows in advance.
    SCOPE = "any-task"

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        self.calls += 1
        if not self.injector.inject(self.SCOPE, self.kind):
            return RunnerResult(task_id=task_id, success=True, output="ok")

        if self.kind is FaultKind.TIMEOUT:
            raise TimeoutError("runner exceeded its deadline")
        if self.kind is FaultKind.PROCESS_KILL:
            raise ProcessLookupError("agent process disappeared")
        if self.kind is FaultKind.MALFORMED_OUTPUT:
            return RunnerResult(
                task_id=task_id, success=False, error="agent returned unparseable output"
            )
        if self.kind is FaultKind.DISCONNECT:
            raise ConnectionResetError("transport closed mid-turn")
        raise AssertionError(f"unhandled fault: {self.kind}")

    async def cancel(self, task_id: str) -> bool:
        return True


class HangingRunner(Runner):
    """Runner that never returns, so a run can be interrupted mid-flight."""

    def __init__(self, started: asyncio.Event, name: str = "hanging") -> None:
        super().__init__(name, list(RunnerCapability))
        self.started = started

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        self.started.set()
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")

    async def cancel(self, task_id: str) -> bool:
        return True


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> AsyncIterator[Path]:
    root = tmp_path / "repo"
    root.mkdir()
    await run_git(root, "init", "--initial-branch=main")
    await run_git(root, "config", "user.email", "test@atlas-flow.invalid")
    await run_git(root, "config", "user.name", "Atlas Flow Test")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    await run_git(root, "add", "-A")
    await run_git(root, "commit", "-m", "initial")
    yield root


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[Persistence]:
    persistence = Persistence(tmp_path / "state.db")
    await persistence.initialize()
    try:
        yield persistence
    finally:
        await persistence.close()


def _config(repo: Path) -> AtlasFlowConfig:
    config = AtlasFlowConfig(project_root=repo)
    config.max_fallback_attempts = 0
    return config


def _event(run_id: str) -> DomainEvent:
    return DomainEvent(
        project_id="atlas-flow", run_id=run_id, type=EventType.STATE_CHANGE
    )


def _plan(goal_id: str = "P09-G01") -> Plan:
    return Plan(goal_id=goal_id, tasks=[TaskNode(id="a", objective="Do the work")])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [
        FaultKind.TIMEOUT,
        FaultKind.PROCESS_KILL,
        FaultKind.MALFORMED_OUTPUT,
        FaultKind.DISCONNECT,
    ],
)
async def test_every_runner_fault_fails_the_task_without_crashing_the_run(
    repo: Path, db: Persistence, kind: FaultKind
) -> None:
    """A misbehaving agent is a failed task, never an exception out of execute()."""
    injector = FaultInjector()
    injector.register(FaultyRunner.SCOPE, FaultPoint(kind=kind, target="*"))
    runner = FaultyRunner(injector, kind)
    harness = Harness(db)
    harness.register(runner)

    report = await GoalRunner(db, harness, _config(repo)).execute(
        _plan(), "rev-1", "faulty"
    )

    assert not report.succeeded
    assert report.run.state == RunState.FAILED

    tasks = await db.load_tasks(report.run.id)
    assert [task.state for task in tasks] == [TaskState.FAILED]

    attempts = await db.load_attempts(report.run.id)
    assert [attempt.state for attempt in attempts] == [AttemptState.FAILED]
    assert attempts[0].error_msg

    evidence = await db.load_evidence("P09-G01")
    assert [item.verdict for item in evidence] == [GateVerdict.FAILED]
    assert evidence[0].gate == GateKind.BUILD


@pytest.mark.asyncio
class TestRecovery:
    async def test_a_run_killed_mid_flight_is_reconciled_not_left_running(
        self, repo: Path, db: Persistence
    ) -> None:
        started = asyncio.Event()
        harness = Harness(db)
        harness.register(HangingRunner(started))

        execution = asyncio.create_task(
            GoalRunner(db, harness, _config(repo)).execute(_plan(), "rev-1", "hanging")
        )
        await asyncio.wait_for(started.wait(), timeout=5)

        # The process dies here: the coroutine never gets to finish anything.
        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution

        run_id = (await db.list_runs())[0].id
        before = await db.load_tasks(run_id)
        assert TaskState.RUNNING in {task.state for task in before}

        report = await recover_run(db, run_id)

        assert report is not None
        assert report.orphaned_tasks
        after = await db.load_tasks(run_id)
        assert TaskState.RUNNING not in {task.state for task in after}
        assert report.run.state == RunState.BLOCKED

        # Cancellation unwinds the harness, so the attempt closed itself. Only
        # the task was left dangling, and only the task needed reconciling.
        attempts = await db.load_attempts(run_id)
        assert [attempt.state for attempt in attempts] == [AttemptState.CANCELLED]
        assert report.orphaned_attempts == []

    async def test_an_attempt_left_running_by_a_hard_kill_is_closed(
        self, repo: Path, db: Persistence
    ) -> None:
        """SIGKILL gives no unwind, so the attempt is still RUNNING on restart."""
        run = Run(project_id="atlas-flow", goal_id="P09-G01", goal_revision="rev-1")
        await db.save_run(run)
        for state in (RunState.PLANNING, RunState.READY, RunState.RUNNING):
            run = await db.record_run_transition(run, state, _event(run.id))

        task = Task(run_id=run.id, objective="Interrupted")
        await db.save_task(task)
        task = await db.record_task_transition(task, TaskState.READY, _event(run.id))
        task = await db.record_task_transition(task, TaskState.RUNNING, _event(run.id))

        attempt = Attempt(task_id=task.id, run_id=run.id, runner="hanging")
        await db.save_attempt(attempt)
        attempt = await db.record_attempt_transition(
            attempt, AttemptState.STARTING, _event(run.id)
        )
        await db.record_attempt_transition(attempt, AttemptState.RUNNING, _event(run.id))

        report = await recover_run(db, run.id)

        assert report is not None
        assert report.orphaned_attempts == [attempt.id]
        assert report.orphaned_tasks == [task.id]
        reloaded = await db.load_attempts(run.id)
        assert [item.state for item in reloaded] == [AttemptState.FAILED]

    async def test_recovery_is_idempotent(self, repo: Path, db: Persistence) -> None:
        """Running it twice must find nothing left, not fail on a closed task."""
        started = asyncio.Event()
        harness = Harness(db)
        harness.register(HangingRunner(started))

        execution = asyncio.create_task(
            GoalRunner(db, harness, _config(repo)).execute(_plan(), "rev-1", "hanging")
        )
        await asyncio.wait_for(started.wait(), timeout=5)
        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution

        run_id = (await db.list_runs())[0].id
        await recover_run(db, run_id)
        second = await recover_run(db, run_id)

        assert second is not None
        assert second.orphaned_tasks == []
        assert second.orphaned_attempts == []

    async def test_state_survives_the_process_that_wrote_it(
        self, repo: Path, db: Persistence, tmp_path: Path
    ) -> None:
        injector = FaultInjector()
        injector.register(FaultyRunner.SCOPE, FaultPoint(kind=FaultKind.TIMEOUT, target="*"))
        harness = Harness(db)
        harness.register(FaultyRunner(injector, FaultKind.TIMEOUT))
        report = await GoalRunner(db, harness, _config(repo)).execute(
            _plan(), "rev-1", "faulty"
        )
        await db.close()

        # A new process opening the same file sees the same history.
        reopened = Persistence(tmp_path / "state.db")
        await reopened.initialize()
        try:
            runs = await reopened.list_runs()
            assert [run.id for run in runs] == [report.run.id]
            assert len(await reopened.load_events(report.run.id)) > 0
            assert await reopened.load_evidence("P09-G01")
        finally:
            await reopened.close()


@pytest.mark.asyncio
class TestConflictFault:
    async def test_a_conflicting_task_is_reported_as_needing_a_human(
        self, repo: Path, db: Persistence
    ) -> None:
        """A merge conflict is a decision, not something to retry."""

        class ConflictingRunner(Runner):
            """Edits its worktree while the target branch moves underneath it."""

            def __init__(self, worktrees: dict[str, Path], root: Path) -> None:
                super().__init__("conflicting", list(RunnerCapability))
                self.worktrees = worktrees
                self.root = root

            async def run(
                self, task_id: str, prompt: str, config: RunnerConfig
            ) -> RunnerResult:
                target = self.worktrees.get(task_id)
                if target is not None:
                    (target / "README.md").write_text(
                        f"rewritten by {task_id}\n", encoding="utf-8"
                    )
                (self.root / "README.md").write_text(
                    "changed on main while the task worked\n", encoding="utf-8"
                )
                await run_git(self.root, "commit", "-am", "diverge on main")
                return RunnerResult(task_id=task_id, success=True, output="ok")

            async def cancel(self, task_id: str) -> bool:
                return True

        class TrackingManager(WorktreeManager):
            def __init__(self, root: Path, sink: dict[str, Path]) -> None:
                super().__init__(root)
                self.sink = sink

            async def create(self, goal_id: str, task_id: str, start_point: str = "HEAD"):  # type: ignore[no-untyped-def]
                worktree = await super().create(goal_id, task_id, start_point)
                self.sink[task_id] = worktree.path
                return worktree

        paths: dict[str, Path] = {}
        harness = Harness(db)
        harness.register(ConflictingRunner(paths, repo))

        plan = Plan(
            goal_id="P09-G01",
            tasks=[TaskNode(id="a", objective="Rewrite the readme",
                            write_scope=["README.md"])],
        )
        manager = TrackingManager(repo, paths)
        runner = GoalRunner(db, harness, _config(repo), worktrees=manager)

        report = await runner.execute(plan, "rev-1", "conflicting")

        assert not report.succeeded
        assert report.conflicts, [outcome.error for outcome in report.outcomes]
        assert report.outcomes[0].needs_human
