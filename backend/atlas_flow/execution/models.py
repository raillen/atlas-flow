"""Execution runtime domain models (P03)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RunState(StrEnum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class TaskState(StrEnum):
    PLANNED = "PLANNED"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class AttemptState(StrEnum):
    CREATED = "CREATED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EventType(StrEnum):
    RUN_STARTED = "atlas.run.started"
    RUN_COMPLETED = "atlas.run.completed"
    RUN_FAILED = "atlas.run.failed"
    TASK_READY = "atlas.task.ready"
    TASK_SUCCEEDED = "atlas.task.succeeded"
    TASK_FAILED = "atlas.task.failed"
    ATTEMPT_STARTED = "atlas.attempt.started"
    ATTEMPT_COMPLETED = "atlas.attempt.completed"
    ATTEMPT_FAILED = "atlas.attempt.failed"
    GATE_PASSED = "atlas.gate.passed"
    GATE_FAILED = "atlas.gate.failed"
    STATE_CHANGE = "atlas.state.change"


# Used when a component was constructed without being told which project it is
# serving. It is deliberately not the name of any real project: a wrong id
# stamped on every event is worse than an obviously missing one.
UNKNOWN_PROJECT = "unknown-project"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class DomainEvent(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("evt"))
    timestamp: str = Field(default_factory=_now_iso)
    project_id: str
    run_id: str | None = None
    type: EventType
    version: int = 1
    payload: dict[str, object] = Field(default_factory=dict)


class Run(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("run"))
    project_id: str
    goal_id: str
    goal_revision: str
    state: RunState = RunState.CREATED
    autonomy: str = "agentic"
    created_at: str = Field(default_factory=_now_iso)
    started_at: str | None = None
    completed_at: str | None = None


class Task(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("task"))
    run_id: str
    objective: str
    role: str | None = None
    risk: str = "medium"
    scope: list[str] = Field(default_factory=list)
    state: TaskState = TaskState.PLANNED
    dependencies: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)


class Attempt(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("att"))
    task_id: str
    run_id: str
    runner: str | None = None
    model_provider: str | None = None
    model_id: str | None = None
    state: AttemptState = AttemptState.CREATED
    created_at: str = Field(default_factory=_now_iso)
    started_at: str | None = None
    completed_at: str | None = None
    error_msg: str | None = None


class RouteDecision(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("route"))
    task_id: str
    candidates: list[str] = Field(default_factory=list)
    selected: str | None = None
    reason: str = ""
    constraints: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)


VALID_TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "run": {
        RunState.CREATED: {RunState.PLANNING},
        RunState.PLANNING: {RunState.READY, RunState.FAILED, RunState.CANCELLED},
        RunState.READY: {RunState.RUNNING, RunState.CANCELLED},
        RunState.RUNNING: {
            RunState.VERIFYING, RunState.BLOCKED,
            RunState.FAILED, RunState.CANCELLED,
        },
        RunState.VERIFYING: {RunState.REVIEWING, RunState.FAILED},
        RunState.REVIEWING: {RunState.COMPLETED, RunState.FAILED},
    },
    "task": {
        TaskState.PLANNED: {TaskState.READY, TaskState.BLOCKED},
        TaskState.READY: {TaskState.RUNNING, TaskState.CANCELLED},
        TaskState.RUNNING: {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED},
        TaskState.SUCCEEDED: {TaskState.SUPERSEDED},
        TaskState.FAILED: {TaskState.READY, TaskState.CANCELLED},
    },
    "attempt": {
        AttemptState.CREATED: {AttemptState.STARTING, AttemptState.CANCELLED},
        AttemptState.STARTING: {AttemptState.RUNNING, AttemptState.FAILED, AttemptState.CANCELLED},
        AttemptState.RUNNING: {AttemptState.COMPLETED, AttemptState.FAILED, AttemptState.CANCELLED},
    },
}


def can_transition(from_state: str, to_state: str, domain: str) -> bool:
    transitions = VALID_TRANSITIONS.get(domain, {})
    allowed = transitions.get(from_state, set())
    return to_state in allowed
