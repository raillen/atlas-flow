"""End-to-end Goal execution: plan -> isolated tasks -> gates -> evidence.

This is the path that turns a validated Plan into real work. It owns the
ordering rules (dependencies, non-overlapping write scopes), the isolation
rules (one worktree per mutating task) and the honesty rules (a task that
cannot be integrated is not a task that succeeded).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.execution.models import Run, RunState, Task, TaskState
from atlas_flow.execution.persistence import Persistence
from atlas_flow.execution.scheduler import Scheduler
from atlas_flow.harness.engine import Harness
from atlas_flow.harness.runner import RunnerConfig
from atlas_flow.planner.dag import DAGError, Plan, TaskNode, validate_dag
from atlas_flow.planner.worktree import (
    IntegrationResult,
    Worktree,
    WorktreeManager,
    WorktreePolicy,
)
from atlas_flow.routing.router import ModelRouter
from atlas_flow.verification.gates import (
    Evidence,
    GateCoordinator,
    GateKind,
    GateVerdict,
)

PROJECT_ID = "atlas-flow"


@dataclass
class TaskOutcome:
    task_id: str
    objective: str
    succeeded: bool
    model_key: str = ""
    attempt_id: str = ""
    worktree: Worktree | None = None
    integration: IntegrationResult | None = None
    error: str = ""

    @property
    def needs_human(self) -> bool:
        """True when the failure is a decision, not a retry."""
        return self.integration is not None and self.integration.has_conflicts


@dataclass
class GoalRunReport:
    run: Run
    outcomes: list[TaskOutcome] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return bool(self.outcomes) and all(o.succeeded for o in self.outcomes)

    @property
    def conflicts(self) -> list[TaskOutcome]:
        return [o for o in self.outcomes if o.needs_human]


class GoalRunner:
    """Executes a Plan for one Goal."""

    def __init__(
        self,
        persistence: Persistence,
        harness: Harness,
        config: AtlasFlowConfig,
        router: ModelRouter | None = None,
        worktrees: WorktreeManager | None = None,
        gates: GateCoordinator | None = None,
    ) -> None:
        self.db = persistence
        self.harness = harness
        self.config = config
        self.router = router or ModelRouter()
        self.worktrees = worktrees
        self.gates = gates or GateCoordinator(persistence)
        self.scheduler = Scheduler(persistence)

    async def execute(
        self,
        plan: Plan,
        goal_revision: str,
        runner_name: str,
        integration_target: str = "main",
    ) -> GoalRunReport:
        errors = validate_dag(plan)
        if errors:
            raise DAGError("; ".join(errors))

        run = Run(
            project_id=PROJECT_ID,
            goal_id=plan.goal_id,
            goal_revision=goal_revision,
            autonomy=self.config.autonomy_mode,
        )
        await self.db.save_run(run)
        run = await self.scheduler.start_run(run)

        tasks, node_by_task_id = _materialize(plan, run.id)
        run, _ = await self.scheduler.schedule_tasks(run, tasks)
        run = await self.scheduler.advance_run(run, RunState.RUNNING)

        report = GoalRunReport(run=run)

        while True:
            ready = await self.scheduler.ready_tasks(run.id)
            if not ready:
                break

            for batch in self._parallel_batches(ready, node_by_task_id):
                results = await asyncio.gather(
                    *(
                        self._run_task(run, task, node_by_task_id[task.id],
                                       runner_name, integration_target)
                        for task in batch
                    )
                )
                report.outcomes.extend(results)

            if any(not outcome.succeeded for outcome in report.outcomes):
                break

        remaining = [
            task.id
            for task in await self.db.load_tasks(run.id)
            if task.state in (TaskState.PLANNED, TaskState.BLOCKED)
        ]
        report.blocked = remaining

        await self.scheduler.evaluate_run_completion(run)
        reloaded = await self.db.load_run(run.id)
        if reloaded is not None:
            report.run = reloaded

        return report

    def _parallel_batches(
        self, ready: list[Task], nodes: dict[str, TaskNode]
    ) -> list[list[Task]]:
        """Group ready tasks so no two in a batch write to overlapping paths."""
        limit = max(1, self.config.max_parallel_tasks)
        batches: list[list[Task]] = []

        for task in ready:
            scope = nodes[task.id].write_scope
            placed = False
            for batch in batches:
                if len(batch) >= limit:
                    continue
                if all(
                    WorktreePolicy.can_coexist(scope, nodes[other.id].write_scope)
                    for other in batch
                ):
                    batch.append(task)
                    placed = True
                    break
            if not placed:
                batches.append([task])
        return batches

    async def _run_task(
        self,
        run: Run,
        task: Task,
        node: TaskNode,
        runner_name: str,
        integration_target: str,
    ) -> TaskOutcome:
        decision = self.router.route(_role_for(node), task_risk=str(node.risk))
        model_key = decision.selected.command_code_id if decision.selected else "default"
        outcome = TaskOutcome(
            task_id=task.id, objective=task.objective, succeeded=False, model_key=model_key
        )

        task = await self.scheduler.mark_task_ready(task)

        worktree: Worktree | None = None
        if self.worktrees and WorktreePolicy.requires_isolation(node.write_scope):
            worktree = await self.worktrees.create(run.goal_id, task.id)
            outcome.worktree = worktree

        result, attempt = await self.harness.execute(
            runner_name,
            task,
            _prompt_for(node),
            RunnerConfig(
                model=model_key,
                max_turns=self.config.command_code_max_turns,
                timeout_seconds=self.config.command_code_timeout_seconds,
            ),
        )
        outcome.attempt_id = attempt.id
        self.router.scorecard.observe(decision.selected.key if decision.selected else
                                      "default", result.success)

        task = await self._reload(task)

        if not result.success:
            outcome.error = result.error or "runner reported failure"
            await self._record_gate(run, task, GateKind.BUILD, GateVerdict.FAILED,
                                    outcome.error)
            await self.scheduler.fail_task(task, outcome.error)
            return outcome

        if worktree and self.worktrees:
            await self.worktrees.commit_all(worktree, f"{task.id}: {task.objective}")
            integration = await self.worktrees.integrate(worktree, integration_target)
            outcome.integration = integration
            if not integration.integrated:
                outcome.error = integration.reason
                await self._record_gate(run, task, GateKind.BUILD, GateVerdict.FAILED,
                                        integration.reason)
                await self.scheduler.fail_task(task, integration.reason)
                return outcome

        await self._record_gate(run, task, GateKind.BUILD, GateVerdict.PASSED,
                                f"attempt {attempt.id} completed")
        await self.scheduler.complete_task(task)
        outcome.succeeded = True
        return outcome

    async def _reload(self, task: Task) -> Task:
        for stored in await self.db.load_tasks(task.run_id):
            if stored.id == task.id:
                return stored
        return task

    async def _record_gate(
        self, run: Run, task: Task, gate: GateKind, verdict: GateVerdict, detail: str
    ) -> None:
        await self.gates.record_evidence(
            Evidence.new(
                goal_id=run.goal_id,
                gate=gate,
                kind="runner_result",
                verdict=verdict,
                uri=detail[:500],
                run_id=run.id,
                task_id=task.id,
            )
        )


def _materialize(plan: Plan, run_id: str) -> tuple[list[Task], dict[str, TaskNode]]:
    """Turn plan nodes into persisted Tasks, rewriting dependency ids.

    Plan nodes carry planner-local ids; Tasks get their own generated ids. The
    dependency lists must be translated, otherwise the scheduler sees
    dependencies that match no task and treats every task as immediately
    ready — running the whole DAG at once.
    """
    tasks = {
        node.id: Task(
            run_id=run_id,
            objective=node.objective,
            role=_role_for(node),
            risk=str(node.risk),
            scope=list(node.write_scope),
        )
        for node in plan.tasks
    }

    for node in plan.tasks:
        tasks[node.id].dependencies = [
            tasks[dependency].id for dependency in node.dependencies
        ]

    node_by_task_id = {tasks[node.id].id: node for node in plan.tasks}
    return list(tasks.values()), node_by_task_id


def _role_for(node: TaskNode) -> str:
    return node.capabilities[0] if node.capabilities else "core-implementer"


def _prompt_for(node: TaskNode) -> str:
    lines = [node.objective]
    if node.write_scope:
        lines.append(f"Write scope: {', '.join(node.write_scope)}")
    if node.gates:
        lines.append(f"Required gates: {', '.join(node.gates)}")
    return "\n".join(lines)


def worktree_manager_for(config: AtlasFlowConfig, repo_root: Path) -> WorktreeManager:
    base = Path(config.worktree_base) if config.worktree_base else config.state_path
    return WorktreeManager(repo_root, base)
