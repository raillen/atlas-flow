"""Goal planner — decomposition contract, DAG validation, concurrency model (P05)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class TaskNode:
    id: str
    objective: str
    dependencies: list[str] = field(default_factory=list)
    write_scope: list[str] = field(default_factory=list)
    gates: list[str] = field(default_factory=list)
    risk: RiskLevel = RiskLevel.MEDIUM
    parallelizable: bool = True
    capabilities: list[str] = field(default_factory=list)


@dataclass
class Plan:
    goal_id: str
    tasks: list[TaskNode]

    def task_by_id(self, task_id: str) -> TaskNode | None:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def downstream_of(self, task_id: str) -> list[TaskNode]:
        return [t for t in self.tasks if task_id in t.dependencies]


class DAGError(Exception):
    """Raised for DAG cycle, missing dependency, or conflict."""


def validate_dag(plan: Plan) -> list[str]:
    """Validate DAG invariants. Returns [] on success, list of error messages otherwise."""
    errors: list[str] = []
    task_ids = {t.id for t in plan.tasks}

    # Dependency closure
    for t in plan.tasks:
        for dep in t.dependencies:
            if dep not in task_ids:
                errors.append(f"Task '{t.id}' depends on unknown task '{dep}'")

    # Cycle detection via DFS coloring: 0=white, 1=gray, 2=black
    color: dict[str, int] = {t.id: 0 for t in plan.tasks}
    adj: dict[str, list[str]] = {t.id: t.dependencies for t in plan.tasks}

    def dfs(u: str) -> bool:
        if u not in color:
            return False
        color[u] = 1
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == 1:
                return True
            if color[v] == 0 and dfs(v):
                return True
        color[u] = 2
        return False

    for task_id in task_ids:
        if color[task_id] == 0 and dfs(task_id):
            errors.append(f"Cycle detected involving task '{task_id}'")
            break

    return errors


def detect_write_scope_conflicts(plan: Plan) -> list[tuple[str, str, str]]:
    """Returns list of (task_a, task_b, path) for overlapping write scopes on parallel tasks."""
    conflicts: list[tuple[str, str, str]] = []
    for i, a in enumerate(plan.tasks):
        for b in plan.tasks[i + 1:]:
            if not _are_concurrent(a, b, plan):
                continue
            for path_a in a.write_scope:
                for path_b in b.write_scope:
                    shared = _shared_prefix(path_a, path_b)
                    if shared:
                        conflicts.append((a.id, b.id, shared))
                        break
                if any(c[0] == a.id and c[1] == b.id for c in conflicts):
                    break
    return conflicts


def _are_concurrent(a: TaskNode, b: TaskNode, plan: Plan) -> bool:
    """Two tasks are concurrent iff neither depends on the other."""
    return a.id not in b.dependencies and b.id not in a.dependencies


def _shared_prefix(a: str, b: str) -> str:
    """Return the longest directory prefix shared by two paths, or '' if none."""
    parts_a = a.strip("/").split("/")
    parts_b = b.strip("/").split("/")
    common = []
    for pa, pb in zip(parts_a, parts_b, strict=False):
        if pa == pb:
            common.append(pa)
        else:
            break
    return "/".join(common)


def dependency_aware_order(plan: Plan) -> list[TaskNode]:
    """Topological sort — tasks with no deps come first."""
    remaining = list(plan.tasks)
    result: list[TaskNode] = []
    completed: set[str] = set()

    while remaining:
        ready = [
            t for t in remaining
            if all(d in completed for d in t.dependencies)
        ]
        if not ready:
            raise DAGError(
                "Cannot resolve execution order: cycle or missing dependency"
            )
        for t in ready:
            result.append(t)
            completed.add(t.id)
            remaining.remove(t)
    return result
