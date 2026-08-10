"""End-to-end Goal execution: plan -> worktrees -> runner -> gates."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.execution.goal_runner import GoalRunner
from atlas_flow.execution.models import RunState, TaskState
from atlas_flow.execution.persistence import Persistence
from atlas_flow.harness.engine import Harness
from atlas_flow.harness.runner import Runner, RunnerConfig, RunnerResult
from atlas_flow.planner.dag import DAGError, Plan, RiskLevel, TaskNode
from atlas_flow.planner.worktree import WorktreeManager, run_git
from atlas_flow.verification.gates import GateKind, GateVerdict


class WritingRunner(Runner):
    """Runner that writes a file into the worktree it was given."""

    def __init__(self, worktrees: dict[str, Path], name: str = "writer") -> None:
        from atlas_flow.harness.runner import RunnerCapability

        super().__init__(name, list(RunnerCapability))
        self.worktrees = worktrees
        self.prompts: list[str] = []

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        self.prompts.append(prompt)
        target = self.worktrees.get(task_id)
        if target is not None:
            (target / f"{task_id}.txt").write_text(prompt, encoding="utf-8")
        return RunnerResult(task_id=task_id, success=True, output="wrote file")

    async def cancel(self, task_id: str) -> bool:
        return True


class BrokenRunner(Runner):
    def __init__(self, name: str = "broken") -> None:
        from atlas_flow.harness.runner import RunnerCapability

        super().__init__(name, list(RunnerCapability))

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        return RunnerResult(task_id=task_id, success=False, error="model refused")

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
    config.max_parallel_tasks = 4
    return config


@pytest.mark.asyncio
class TestGoalExecution:
    async def test_plan_runs_to_completion_and_integrates_work(
        self, repo: Path, db: Persistence
    ) -> None:
        worktree_paths: dict[str, Path] = {}
        runner = WritingRunner(worktree_paths)
        harness = Harness(db)
        harness.register(runner)

        manager = _TrackingWorktreeManager(repo, worktree_paths)
        goal_runner = GoalRunner(
            db, harness, _config(repo), worktrees=manager
        )

        plan = Plan(
            goal_id="P05-G01",
            tasks=[
                TaskNode(id="a", objective="Write module a", write_scope=["src/a"]),
                TaskNode(id="b", objective="Write module b", write_scope=["src/b"]),
            ],
        )

        report = await goal_runner.execute(plan, "rev-1", "writer")

        assert report.succeeded, [o.error for o in report.outcomes]
        assert report.run.state == RunState.VERIFYING
        assert len(report.outcomes) == 2

        # Both task branches were merged into main.
        log = await run_git(repo, "log", "--oneline", "main")
        assert log.count("Integrate atlas/P05-G01/") == 2
        committed = await run_git(repo, "ls-files")
        assert committed.count(".txt") == 2

        stored = await db.load_tasks(report.run.id)
        assert {t.state for t in stored} == {TaskState.SUCCEEDED}
        assert len(await db.load_attempts(report.run.id)) == 2

    async def test_dependencies_are_respected(
        self, repo: Path, db: Persistence
    ) -> None:
        order: list[str] = []

        class OrderedRunner(WritingRunner):
            async def run(
                self, task_id: str, prompt: str, config: RunnerConfig
            ) -> RunnerResult:
                order.append(prompt.splitlines()[0])
                return await super().run(task_id, prompt, config)

        worktree_paths: dict[str, Path] = {}
        harness = Harness(db)
        harness.register(OrderedRunner(worktree_paths, "writer"))

        goal_runner = GoalRunner(
            db, harness, _config(repo),
            worktrees=_TrackingWorktreeManager(repo, worktree_paths),
        )

        plan = Plan(
            goal_id="P05-G01",
            tasks=[
                TaskNode(id="second", objective="Second", dependencies=["first"],
                         write_scope=["src/second"]),
                TaskNode(id="first", objective="First", write_scope=["src/first"]),
            ],
        )

        report = await goal_runner.execute(plan, "rev-1", "writer")

        assert report.succeeded, [o.error for o in report.outcomes]
        assert order == ["First", "Second"]

    async def test_overlapping_write_scopes_are_not_run_together(
        self, repo: Path, db: Persistence
    ) -> None:
        """Two independent tasks writing the same subtree must be serialized."""
        concurrent = 0
        peak = 0

        class CountingRunner(WritingRunner):
            async def run(
                self, task_id: str, prompt: str, config: RunnerConfig
            ) -> RunnerResult:
                nonlocal concurrent, peak
                concurrent += 1
                peak = max(peak, concurrent)
                try:
                    return await super().run(task_id, prompt, config)
                finally:
                    concurrent -= 1

        worktree_paths: dict[str, Path] = {}
        harness = Harness(db)
        harness.register(CountingRunner(worktree_paths, "writer"))

        goal_runner = GoalRunner(
            db, harness, _config(repo),
            worktrees=_TrackingWorktreeManager(repo, worktree_paths),
        )

        plan = Plan(
            goal_id="P05-G01",
            tasks=[
                TaskNode(id="a", objective="A", write_scope=["backend/auth"]),
                TaskNode(id="b", objective="B", write_scope=["backend/auth/session"]),
            ],
        )

        report = await goal_runner.execute(plan, "rev-1", "writer")

        assert report.succeeded, [o.error for o in report.outcomes]
        assert peak == 1

    async def test_failed_runner_fails_the_task_and_records_evidence(
        self, repo: Path, db: Persistence
    ) -> None:
        harness = Harness(db)
        harness.register(BrokenRunner("broken"))

        goal_runner = GoalRunner(db, harness, _config(repo))
        plan = Plan(
            goal_id="P05-G01",
            tasks=[TaskNode(id="a", objective="Will fail", risk=RiskLevel.HIGH)],
        )

        report = await goal_runner.execute(plan, "rev-1", "broken")

        assert not report.succeeded
        assert report.outcomes[0].error == "model refused"
        assert report.run.state == RunState.FAILED

        evidence = await db.load_evidence("P05-G01")
        assert [e.verdict for e in evidence] == [GateVerdict.FAILED]
        assert evidence[0].gate == GateKind.BUILD

    async def test_invalid_dag_is_rejected_before_any_run_starts(
        self, repo: Path, db: Persistence
    ) -> None:
        harness = Harness(db)
        goal_runner = GoalRunner(db, harness, _config(repo))
        plan = Plan(
            goal_id="P05-G01",
            tasks=[
                TaskNode(id="a", objective="A", dependencies=["b"]),
                TaskNode(id="b", objective="B", dependencies=["a"]),
            ],
        )

        with pytest.raises(DAGError, match="Cycle detected"):
            await goal_runner.execute(plan, "rev-1", "dummy")

        assert await db.list_runs() == []


class _TrackingWorktreeManager(WorktreeManager):
    """Worktree manager that tells the test runner where each task checked out."""

    def __init__(self, repo_root: Path, sink: dict[str, Path]) -> None:
        super().__init__(repo_root)
        self.sink = sink

    async def create(self, goal_id: str, task_id: str, start_point: str = "HEAD"):  # type: ignore[no-untyped-def]
        worktree = await super().create(goal_id, task_id, start_point)
        self.sink[task_id] = worktree.path
        return worktree
