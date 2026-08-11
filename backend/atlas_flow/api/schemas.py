"""Wire shapes for the desktop client.

These are deliberately separate from the domain models: the UI reads a stable
projection, and renaming a field in the runtime does not silently reshape the
API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from atlas_flow.execution.models import Attempt, DomainEvent, Run, Task
from atlas_flow.goals.models import Goal
from atlas_flow.verification.gates import Evidence


class GoalView(BaseModel):
    id: str
    phase: str
    title: str
    state: str
    objective: str
    acceptance: list[str]
    gates: dict[str, str]
    dependencies: list[str]
    evidence_count: int

    @staticmethod
    def of(goal: Goal) -> GoalView:
        return GoalView(
            id=goal.id,
            phase=goal.phase,
            title=goal.title,
            state=goal.state,
            objective=goal.objective,
            acceptance=goal.acceptance,
            gates=goal.gates.model_dump(),
            dependencies=goal.dependencies,
            evidence_count=len(goal.evidence),
        )


class TaskView(BaseModel):
    id: str
    objective: str
    state: str
    role: str | None
    risk: str
    scope: list[str]
    dependencies: list[str]

    @staticmethod
    def of(task: Task) -> TaskView:
        return TaskView(
            id=task.id,
            objective=task.objective,
            state=str(task.state),
            role=task.role,
            risk=task.risk,
            scope=task.scope,
            dependencies=task.dependencies,
        )


class AttemptView(BaseModel):
    id: str
    task_id: str
    runner: str | None
    model_id: str | None
    state: str
    started_at: str | None
    completed_at: str | None
    error_msg: str | None

    @staticmethod
    def of(attempt: Attempt) -> AttemptView:
        return AttemptView(
            id=attempt.id,
            task_id=attempt.task_id,
            runner=attempt.runner,
            model_id=attempt.model_id,
            state=str(attempt.state),
            started_at=attempt.started_at,
            completed_at=attempt.completed_at,
            error_msg=attempt.error_msg,
        )


class EventView(BaseModel):
    id: str
    timestamp: str
    type: str
    # Which project produced this. Atlas Flow runs against whatever project it
    # was opened on, so an event that cannot name its project is unattributable.
    project_id: str
    run_id: str | None
    payload: dict[str, object]

    @staticmethod
    def of(event: DomainEvent) -> EventView:
        return EventView(
            id=event.id,
            timestamp=event.timestamp,
            type=str(event.type),
            project_id=event.project_id,
            run_id=event.run_id,
            payload=event.payload,
        )


class EvidenceView(BaseModel):
    id: str
    gate: str
    kind: str
    verdict: str
    uri: str
    task_id: str | None
    attached_at: str

    @staticmethod
    def of(evidence: Evidence) -> EvidenceView:
        return EvidenceView(
            id=evidence.id,
            gate=str(evidence.gate),
            kind=evidence.kind,
            verdict=str(evidence.verdict),
            uri=evidence.uri,
            task_id=evidence.task_id,
            attached_at=evidence.attached_at,
        )


class RunView(BaseModel):
    id: str
    goal_id: str
    goal_revision: str
    state: str
    autonomy: str
    created_at: str
    task_count: int = 0

    @staticmethod
    def of(run: Run, task_count: int = 0) -> RunView:
        return RunView(
            id=run.id,
            goal_id=run.goal_id,
            goal_revision=run.goal_revision,
            state=str(run.state),
            autonomy=run.autonomy,
            created_at=run.created_at,
            task_count=task_count,
        )


class RunDetail(BaseModel):
    run: RunView
    tasks: list[TaskView] = Field(default_factory=list)
    attempts: list[AttemptView] = Field(default_factory=list)
    events: list[EventView] = Field(default_factory=list)


class GateView(BaseModel):
    gate: str
    requirement: str
    verdict: str
    evidence_ids: list[str] = Field(default_factory=list)
    details: str = ""


class GoalVerification(BaseModel):
    goal_id: str
    gates: list[GateView] = Field(default_factory=list)
    evidence: list[EvidenceView] = Field(default_factory=list)
    completable: bool = False
    blocking: str = ""


class CreateRunRequest(BaseModel):
    goal_id: str
    runner: str = "dummy"
    integration_target: str = "main"


class ModelStatsView(BaseModel):
    model_key: str
    uses: int
    successes: int
    failures: int
    success_rate: float
    average_latency_ms: float


class RoleRouteView(BaseModel):
    role: str
    selected: str | None
    provider: str | None
    explanation: str
    fallback_attempts: int


class RoutingView(BaseModel):
    state: str  # "pending" | "reachable" | "degraded"
    reachable: bool
    degraded: bool
    reason: str
    probed_at: str
    available: list[str] = Field(default_factory=list)
    roles: list[RoleRouteView] = Field(default_factory=list)
    stats: list[ModelStatsView] = Field(default_factory=list)


class MessageRequest(BaseModel):
    content: str
    turn_type: str = "message"


class DecisionRequest(BaseModel):
    title: str
    statement: str
    rationale: str
    affected_domains: list[str] = Field(default_factory=list)
    requires_adr: bool = False


class DocEntry(BaseModel):
    path: str
    title: str
    section: str


class DocContent(BaseModel):
    path: str
    content: str
