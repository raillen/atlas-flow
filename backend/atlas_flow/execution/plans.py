"""Durable, reviewable plan snapshots."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from atlas_flow.planner.dag import RiskLevel, TaskNode

if TYPE_CHECKING:
    from atlas_flow.planner.dag import Plan


class PlanState(StrEnum):
    DRAFT = "DRAFT"
    LOCKED = "LOCKED"
    CONSUMED = "CONSUMED"


class PlanTask(BaseModel):
    id: str
    objective: str
    dependencies: list[str] = Field(default_factory=list)
    write_scope: list[str] = Field(default_factory=list)
    gates: list[str] = Field(default_factory=list)
    risk: RiskLevel = RiskLevel.MEDIUM
    parallelizable: bool = True
    capabilities: list[str] = Field(default_factory=list)

    @staticmethod
    def of(task: TaskNode) -> PlanTask:
        return PlanTask(
            id=task.id,
            objective=task.objective,
            dependencies=list(task.dependencies),
            write_scope=list(task.write_scope),
            gates=list(task.gates),
            risk=task.risk,
            parallelizable=task.parallelizable,
            capabilities=list(task.capabilities),
        )

    def to_task_node(self) -> TaskNode:
        return TaskNode(
            id=self.id,
            objective=self.objective,
            dependencies=list(self.dependencies),
            write_scope=list(self.write_scope),
            gates=list(self.gates),
            risk=self.risk,
            parallelizable=self.parallelizable,
            capabilities=list(self.capabilities),
        )


class PlanRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:12]}")
    project_id: str
    goal_id: str
    goal_revision: str
    state: PlanState = PlanState.DRAFT
    autonomy: str = "agentic"
    runner: str = "dummy"
    integration_target: str = "main"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    tasks: list[PlanTask] = Field(default_factory=list)

    def to_plan(self) -> Plan:
        from atlas_flow.planner.dag import Plan

        return Plan(goal_id=self.goal_id, tasks=[task.to_task_node() for task in self.tasks])
