"""End-to-end Goal execution: plan -> isolated tasks -> gates -> evidence.

This is the path that turns a validated Plan into real work. It owns the
ordering rules (dependencies, non-overlapping write scopes), the isolation
rules (one worktree per mutating task) and the honesty rules (a task that
cannot be integrated is not a task that succeeded).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.execution.budget import BudgetExceeded, BudgetLedger, Usage
from atlas_flow.execution.models import Attempt, Run, RunState, Task, TaskState
from atlas_flow.execution.persistence import Persistence
from atlas_flow.execution.scheduler import Scheduler
from atlas_flow.harness.engine import Harness
from atlas_flow.harness.runner import RunnerConfig, RunnerResult
from atlas_flow.planner.dag import DAGError, Plan, RiskLevel, TaskNode, validate_dag
from atlas_flow.planner.worktree import (
    IntegrationResult,
    Worktree,
    WorktreeManager,
    WorktreePolicy,
)
from atlas_flow.routing.router import ModelEntry, ModelRouter, RouteDecision
from atlas_flow.routing.store import RoutingStore
from atlas_flow.verification.gates import (
    Evidence,
    GateCoordinator,
    GateKind,
    GateVerdict,
)


@dataclass
class TaskOutcome:
    task_id: str
    objective: str
    succeeded: bool
    model_key: str = ""
    provider: str = ""
    attempt_id: str = ""
    fallback_attempts: int = 0
    budget_stopped: bool = False
    reviewer_model_key: str = ""
    review_verdict: str = ""
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
    budget: BudgetLedger | None = None

    @property
    def succeeded(self) -> bool:
        return bool(self.outcomes) and all(o.succeeded for o in self.outcomes)

    @property
    def conflicts(self) -> list[TaskOutcome]:
        return [o for o in self.outcomes if o.needs_human]

    @property
    def stopped_by_budget(self) -> bool:
        return any(o.budget_stopped for o in self.outcomes)


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
        routing_store: RoutingStore | None = None,
    ) -> None:
        self.db = persistence
        self.harness = harness
        self.config = config
        self.router = router or ModelRouter()
        self.worktrees = worktrees
        self.gates = gates or GateCoordinator(persistence)
        self.routing_store = routing_store
        self.scheduler = Scheduler(persistence, config.project_id)
        self.budget: BudgetLedger | None = None

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
            project_id=self.config.project_id,
            goal_id=plan.goal_id,
            goal_revision=goal_revision,
            autonomy=self.config.autonomy_mode,
        )
        await self.db.save_run(run)
        run = await self.scheduler.start_run(run)

        tasks, node_by_task_id = _materialize(plan, run.id)
        self.budget = BudgetLedger.from_config(self.config, len(tasks))
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

        report.budget = self.budget
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
        role = _role_for(node)
        decision = self.router.route(role, task_risk=str(node.risk))
        outcome = TaskOutcome(task_id=task.id, objective=task.objective, succeeded=False)

        if self.routing_store is not None:
            await self.routing_store.record_decision(decision, task.id, run.id)

        task = await self.scheduler.mark_task_ready(task)

        worktree: Worktree | None = None
        if self.worktrees and WorktreePolicy.requires_isolation(node.write_scope):
            worktree = await self.worktrees.create(run.goal_id, task.id)
            outcome.worktree = worktree

        result, attempt = await self._attempt_with_fallback(
            run, task, node, role, decision, runner_name, outcome
        )

        task = await self._reload(task)

        if result is None or attempt is None:
            # The budget stopped this task before it could be tried again.
            await self._record_gate(run, task, GateKind.BUILD, GateVerdict.FAILED,
                                    outcome.error)
            if task.state == TaskState.RUNNING:
                await self.scheduler.fail_task(task, outcome.error)
            return outcome

        if not result.success:
            outcome.error = result.error or "runner reported failure"
            await self._record_gate(run, task, GateKind.BUILD, GateVerdict.FAILED,
                                    outcome.error)
            await self.scheduler.fail_task(task, outcome.error)
            return outcome

        # High-risk work is reviewed before it is merged, not after: a change
        # that a reviewer rejects must never have reached the target branch.
        if _is_high_risk(node) and not await self._cross_provider_review(
            run, task, node, outcome, runner_name, worktree
        ):
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

    async def _attempt_with_fallback(
        self,
        run: Run,
        task: Task,
        node: TaskNode,
        role: str,
        decision: RouteDecision,
        runner_name: str,
        outcome: TaskOutcome,
    ) -> tuple[RunnerResult | None, Attempt | None]:
        """Try the routed model, then fall back down the candidate list.

        Fallback is bounded twice over: by `max_fallback_attempts`, and by the
        number of models that are actually reachable. Retrying the same
        unreachable model forever is the failure mode this guards against.
        """
        candidates = _fallback_candidates(self.router, decision)
        limit = min(len(candidates), 1 + max(0, self.config.max_fallback_attempts))

        last_result: RunnerResult | None = None
        last_attempt: Attempt | None = None

        for index, candidate in enumerate(candidates[:limit]):
            model_id = candidate.command_code_id if candidate else "default"
            model_key = candidate.key if candidate else "default"

            if self.budget is not None:
                try:
                    self.budget.check_can_start_attempt()
                except BudgetExceeded as exc:
                    outcome.error = str(exc)
                    outcome.budget_stopped = True
                    return last_result, last_attempt

            started = time.monotonic()
            result, attempt = await self.harness.execute(
                runner_name,
                task,
                _prompt_for(node),
                RunnerConfig(
                    model=model_id,
                    max_turns=self.config.command_code_max_turns,
                    timeout_seconds=self.config.command_code_timeout_seconds,
                    role=role,
                ),
            )
            latency_ms = (time.monotonic() - started) * 1000

            last_result, last_attempt = result, attempt
            outcome.attempt_id = attempt.id
            outcome.model_key = model_id
            outcome.provider = candidate.provider if candidate else ""
            outcome.fallback_attempts = index

            usage = Usage.from_result(result)
            if self.budget is not None:
                self.budget.record(usage)

            self.router.scorecard.observe(model_key, result.success, latency_ms)
            if self.routing_store is not None:
                await self.routing_store.record_observation(
                    model_key, result.success, role=role, latency_ms=latency_ms,
                    run_id=run.id, task_id=task.id,
                )

            if result.success:
                return result, attempt

            outcome.error = result.error or "runner reported failure"
            task = await self._reload(task)
            if index + 1 < limit and task.state == TaskState.FAILED:
                # A failed task is retryable; put it back in flight for the
                # next candidate rather than leaving it closed.
                task = await self.scheduler.mark_task_ready(task)

        return last_result, last_attempt

    async def _cross_provider_review(
        self,
        run: Run,
        task: Task,
        node: TaskNode,
        outcome: TaskOutcome,
        runner_name: str,
        worktree: Worktree | None,
    ) -> bool:
        """Have a different provider check high-risk work before it is merged.

        Two models from one provider share their training and their blind
        spots, so a review only adds information when it comes from somewhere
        else. When no other provider is reachable the task is not blocked — the
        policy says cross-provider review "when possible" — but the review gate
        stays PENDING, so unreviewed work is never recorded as reviewed.
        """
        reviewer = self.router.select_high_risk_reviewer(outcome.provider)
        if reviewer is None:
            await self._record_gate(
                run, task, GateKind.REVIEW, GateVerdict.PENDING,
                f"No reviewer outside provider "
                f"'{outcome.provider or 'unknown'}' is reachable",
                kind="review_comment",
            )
            return True

        if self.budget is not None:
            try:
                self.budget.check_can_start_attempt()
            except BudgetExceeded as exc:
                await self._record_gate(
                    run, task, GateKind.REVIEW, GateVerdict.PENDING, str(exc),
                    kind="review_comment",
                )
                return True

        started = time.monotonic()
        result, attempt = await self.harness.execute(
            runner_name,
            task,
            _review_prompt(node, worktree),
            RunnerConfig(
                model=reviewer.command_code_id,
                max_turns=self.config.command_code_max_turns,
                timeout_seconds=self.config.command_code_timeout_seconds,
                role="reviewer",
            ),
        )
        latency_ms = (time.monotonic() - started) * 1000

        if self.budget is not None:
            self.budget.record(Usage.from_result(result))
        self.router.scorecard.observe(reviewer.key, result.success, latency_ms)
        if self.routing_store is not None:
            await self.routing_store.record_observation(
                reviewer.key, result.success, role="reviewer", latency_ms=latency_ms,
                run_id=run.id, task_id=task.id,
            )

        outcome.reviewer_model_key = reviewer.command_code_id
        outcome.review_verdict = str(
            GateVerdict.PASSED if result.success else GateVerdict.FAILED
        )
        detail = (
            f"{reviewer.key} ({reviewer.provider}) reviewed attempt {attempt.id}"
        )
        if not result.success:
            outcome.error = result.error or "cross-provider review rejected the change"
            detail = f"{detail}: {outcome.error}"

        await self._record_gate(
            run, task, GateKind.REVIEW,
            GateVerdict.PASSED if result.success else GateVerdict.FAILED,
            detail, kind="review_comment",
        )
        return result.success

    async def _reload(self, task: Task) -> Task:
        for stored in await self.db.load_tasks(task.run_id):
            if stored.id == task.id:
                return stored
        return task

    async def _record_gate(
        self,
        run: Run,
        task: Task,
        gate: GateKind,
        verdict: GateVerdict,
        detail: str,
        kind: str = "runner_result",
    ) -> None:
        await self.gates.record_evidence(
            Evidence.new(
                goal_id=run.goal_id,
                gate=gate,
                kind=kind,
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


def _fallback_candidates(
    router: ModelRouter, decision: RouteDecision
) -> list[ModelEntry | None]:
    """The selected model first, then the other reachable candidates.

    A model the registry does not expose is not a fallback; trying it just
    burns an attempt. When nothing is reachable the list holds a single `None`,
    which runs the harness on its default model — the runner may still be able
    to work without the router picking for it.
    """
    reachable = [
        candidate for candidate in decision.candidates if router.is_reachable(candidate)
    ]
    if decision.selected is not None:
        reachable = [decision.selected] + [
            candidate for candidate in reachable if candidate.key != decision.selected.key
        ]
    return list(reachable) if reachable else [None]


def _is_high_risk(node: TaskNode) -> bool:
    return str(node.risk) == str(RiskLevel.HIGH)


def _review_prompt(node: TaskNode, worktree: Worktree | None) -> str:
    lines = [
        "Review the change made for this task. Reject it if it is incorrect,"
        " unsafe, or reaches outside its write scope.",
        f"Objective: {node.objective}",
    ]
    if node.write_scope:
        lines.append(f"Write scope: {', '.join(node.write_scope)}")
    if worktree is not None:
        lines.append(f"Worktree: {worktree.path}")
        lines.append(f"Branch: {worktree.branch}")
    return "\n".join(lines)


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
