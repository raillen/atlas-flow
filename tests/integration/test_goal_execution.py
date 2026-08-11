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
from atlas_flow.routing.router import ModelRouter
from atlas_flow.routing.store import RoutingStore
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


class ModelAwareRunner(Runner):
    """Runner that succeeds only for the models it was told to accept."""

    def __init__(self, accepts: set[str], name: str = "picky") -> None:
        from atlas_flow.harness.runner import RunnerCapability

        super().__init__(name, list(RunnerCapability))
        self.accepts = accepts
        self.models: list[str] = []

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        self.models.append(config.model)
        if config.model in self.accepts:
            return RunnerResult(
                task_id=task_id, success=True, output="ok",
                evidence={"tokens": "100", "cost_usd": "0.01"},
            )
        return RunnerResult(
            task_id=task_id, success=False, error=f"{config.model} unavailable",
            evidence={"tokens": "10", "cost_usd": "0.001"},
        )

    async def cancel(self, task_id: str) -> bool:
        return True


@pytest.mark.asyncio
class TestFallbackAndBudget:
    """P08: a failed model is retried on a different one, but not forever."""

    async def test_a_failing_model_falls_back_to_another_provider(
        self, repo: Path, db: Persistence
    ) -> None:
        runner = ModelAwareRunner({"deepseek/deepseek-v4-pro"})
        harness = Harness(db)
        harness.register(runner)

        routing = RoutingStore(db)
        await routing.initialize()

        goal_runner = GoalRunner(db, harness, _config(repo), routing_store=routing)
        plan = Plan(goal_id="P08-G01", tasks=[TaskNode(id="a", objective="Implement")])

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert report.succeeded, [o.error for o in report.outcomes]
        # The role prefers xiaomi; it failed, so the run crossed to deepseek.
        assert runner.models == ["xiaomi/mimo-v2.5-pro", "deepseek/deepseek-v4-pro"]
        outcome = report.outcomes[0]
        assert outcome.model_key == "deepseek/deepseek-v4-pro"
        assert outcome.fallback_attempts == 1
        assert len(await db.load_attempts(report.run.id)) == 2

        # Both models were observed, so the next run routes on evidence.
        stats = {s.model_key: s for s in await routing.stats()}
        assert stats["mimo-v2.5-pro"].failures == 1
        assert stats["deepseek-v4-pro"].successes == 1

    async def test_fallback_stops_at_the_configured_limit(
        self, repo: Path, db: Persistence
    ) -> None:
        runner = ModelAwareRunner(set())
        harness = Harness(db)
        harness.register(runner)

        config = _config(repo)
        config.max_fallback_attempts = 0
        goal_runner = GoalRunner(db, harness, config)
        plan = Plan(goal_id="P08-G01", tasks=[TaskNode(id="a", objective="Implement")])

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert not report.succeeded
        assert runner.models == ["xiaomi/mimo-v2.5-pro"]

    async def test_fallback_stops_when_no_further_model_is_reachable(
        self, repo: Path, db: Persistence
    ) -> None:
        """A generous fallback budget cannot invent models to try."""
        runner = ModelAwareRunner(set())
        harness = Harness(db)
        harness.register(runner)

        config = _config(repo)
        config.max_fallback_attempts = 10
        goal_runner = GoalRunner(db, harness, config)
        plan = Plan(goal_id="P08-G01", tasks=[TaskNode(id="a", objective="Implement")])

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert not report.succeeded
        # Only the two 'expected' models are reachable without a live probe.
        assert runner.models == ["xiaomi/mimo-v2.5-pro", "deepseek/deepseek-v4-pro"]

    async def test_the_attempt_budget_stops_a_run_before_the_fallback_list_ends(
        self, repo: Path, db: Persistence
    ) -> None:
        runner = ModelAwareRunner(set())
        harness = Harness(db)
        harness.register(runner)

        config = _config(repo)
        config.max_fallback_attempts = 5
        config.max_retries_per_task = 0  # one attempt per task, and no more
        goal_runner = GoalRunner(db, harness, config)
        plan = Plan(goal_id="P08-G01", tasks=[TaskNode(id="a", objective="Implement")])

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert not report.succeeded
        assert report.stopped_by_budget
        assert runner.models == ["xiaomi/mimo-v2.5-pro"]
        assert report.budget is not None
        assert report.budget.summary()["attempts"] == 1
        assert report.budget.remaining_attempts() == 0

    async def test_reported_usage_is_accumulated_across_attempts(
        self, repo: Path, db: Persistence
    ) -> None:
        runner = ModelAwareRunner({"deepseek/deepseek-v4-pro"})
        harness = Harness(db)
        harness.register(runner)

        goal_runner = GoalRunner(db, harness, _config(repo))
        plan = Plan(goal_id="P08-G01", tasks=[TaskNode(id="a", objective="Implement")])

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert report.budget is not None
        summary = report.budget.summary()
        assert summary["tokens"] == 110  # 10 for the failure, 100 for the success
        assert summary["spend_is_measured"] is True


@pytest.mark.asyncio
class TestCrossProviderReview:
    """P08: high-risk work is checked by a model from a different provider."""

    async def test_high_risk_work_is_reviewed_by_another_provider(
        self, repo: Path, db: Persistence
    ) -> None:
        runner = ModelAwareRunner(
            {"xiaomi/mimo-v2.5-pro", "deepseek/deepseek-v4-pro"}
        )
        harness = Harness(db)
        harness.register(runner)

        goal_runner = GoalRunner(db, harness, _config(repo))
        plan = Plan(
            goal_id="P08-G01",
            tasks=[TaskNode(id="a", objective="Touch auth", risk=RiskLevel.HIGH)],
        )

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert report.succeeded, [o.error for o in report.outcomes]
        outcome = report.outcomes[0]
        assert outcome.model_key == "xiaomi/mimo-v2.5-pro"
        assert outcome.reviewer_model_key == "deepseek/deepseek-v4-pro"
        assert outcome.review_verdict == "PASSED"
        # Implementation and review are separate, persisted attempts.
        assert runner.models == [
            "xiaomi/mimo-v2.5-pro", "deepseek/deepseek-v4-pro"
        ]
        assert len(await db.load_attempts(report.run.id)) == 2

        review = [
            e for e in await db.load_evidence("P08-G01") if e.gate == GateKind.REVIEW
        ]
        assert [e.verdict for e in review] == [GateVerdict.PASSED]
        assert review[0].kind == "review_comment"

    async def test_a_rejected_review_fails_the_task_and_merges_nothing(
        self, repo: Path, db: Persistence
    ) -> None:
        # The implementer's model works; the reviewer's rejects the change.
        runner = ModelAwareRunner({"xiaomi/mimo-v2.5-pro"})
        harness = Harness(db)
        harness.register(runner)

        worktree_paths: dict[str, Path] = {}
        goal_runner = GoalRunner(
            db, harness, _config(repo),
            worktrees=_TrackingWorktreeManager(repo, worktree_paths),
        )
        plan = Plan(
            goal_id="P08-G01",
            tasks=[
                TaskNode(id="a", objective="Touch auth", risk=RiskLevel.HIGH,
                         write_scope=["backend/auth"]),
            ],
        )

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert not report.succeeded
        assert report.outcomes[0].review_verdict == "FAILED"
        assert "unavailable" in report.outcomes[0].error

        # Rejected work never reached the target branch.
        log = await run_git(repo, "log", "--oneline", "main")
        assert "Integrate atlas/" not in log

        stored = await db.load_tasks(report.run.id)
        assert [t.state for t in stored] == [TaskState.FAILED]

    async def test_ordinary_risk_work_is_not_reviewed(
        self, repo: Path, db: Persistence
    ) -> None:
        runner = ModelAwareRunner({"xiaomi/mimo-v2.5-pro"})
        harness = Harness(db)
        harness.register(runner)

        goal_runner = GoalRunner(db, harness, _config(repo))
        plan = Plan(
            goal_id="P08-G01",
            tasks=[TaskNode(id="a", objective="Tidy up", risk=RiskLevel.LOW)],
        )

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert report.succeeded
        assert report.outcomes[0].reviewer_model_key == ""
        assert runner.models == ["xiaomi/mimo-v2.5-pro"]
        assert not [
            e for e in await db.load_evidence("P08-G01") if e.gate == GateKind.REVIEW
        ]

    async def test_without_a_second_provider_the_review_gate_stays_pending(
        self, repo: Path, db: Persistence
    ) -> None:
        """"When possible" — an unreviewable change is not a reviewed one."""
        runner = ModelAwareRunner({"xiaomi/mimo-v2.5-pro"})
        harness = Harness(db)
        harness.register(runner)

        only_xiaomi = ModelRouter(available_models=["xiaomi/mimo-v2.5-pro"])
        goal_runner = GoalRunner(db, harness, _config(repo), router=only_xiaomi)
        plan = Plan(
            goal_id="P08-G01",
            tasks=[TaskNode(id="a", objective="Touch auth", risk=RiskLevel.HIGH)],
        )

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert report.succeeded, [o.error for o in report.outcomes]
        assert report.outcomes[0].reviewer_model_key == ""
        review = [
            e for e in await db.load_evidence("P08-G01") if e.gate == GateKind.REVIEW
        ]
        assert [e.verdict for e in review] == [GateVerdict.PENDING]
        assert "No reviewer outside provider 'xiaomi'" in review[0].uri

    async def test_a_spent_budget_does_not_forge_a_review(
        self, repo: Path, db: Persistence
    ) -> None:
        runner = ModelAwareRunner({"xiaomi/mimo-v2.5-pro"})
        harness = Harness(db)
        harness.register(runner)

        config = _config(repo)
        config.max_retries_per_task = 0  # one attempt total: nothing left to review with
        goal_runner = GoalRunner(db, harness, config)
        plan = Plan(
            goal_id="P08-G01",
            tasks=[TaskNode(id="a", objective="Touch auth", risk=RiskLevel.HIGH)],
        )

        report = await goal_runner.execute(plan, "rev-1", "picky")

        assert report.succeeded
        assert runner.models == ["xiaomi/mimo-v2.5-pro"]
        review = [
            e for e in await db.load_evidence("P08-G01") if e.gate == GateKind.REVIEW
        ]
        assert [e.verdict for e in review] == [GateVerdict.PENDING]
        assert "Budget exceeded" in review[0].uri


class _TrackingWorktreeManager(WorktreeManager):
    """Worktree manager that tells the test runner where each task checked out."""

    def __init__(self, repo_root: Path, sink: dict[str, Path]) -> None:
        super().__init__(repo_root)
        self.sink = sink

    async def create(self, goal_id: str, task_id: str, start_point: str = "HEAD"):  # type: ignore[no-untyped-def]
        worktree = await super().create(goal_id, task_id, start_point)
        self.sink[task_id] = worktree.path
        return worktree
