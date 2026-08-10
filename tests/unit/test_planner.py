"""P05 Planner DAG and worktree tests."""

import pytest

from atlas_flow.planner.dag import (
    DAGError,
    Plan,
    TaskNode,
    dependency_aware_order,
    detect_write_scope_conflicts,
    validate_dag,
)
from atlas_flow.planner.worktree import (
    WorktreePolicy,
    worktree_branch_name,
    worktree_directory,
)


class TestDAGValidation:
    def test_valid_linear_dag(self) -> None:
        plan = Plan(
            goal_id="G1",
            tasks=[
                TaskNode(id="T1", objective="Setup"),
                TaskNode(id="T2", objective="Build", dependencies=["T1"]),
                TaskNode(id="T3", objective="Test", dependencies=["T2"]),
            ],
        )
        assert validate_dag(plan) == []

    def test_cycle_detected(self) -> None:
        plan = Plan(
            goal_id="G1",
            tasks=[
                TaskNode(id="A", objective="A", dependencies=["C"]),
                TaskNode(id="B", objective="B", dependencies=["A"]),
                TaskNode(id="C", objective="C", dependencies=["B"]),
            ],
        )
        errors = validate_dag(plan)
        assert len(errors) >= 1
        assert any("cycle" in e.lower() for e in errors)

    def test_missing_dependency_reported(self) -> None:
        plan = Plan(
            goal_id="G1",
            tasks=[
                TaskNode(id="T1", objective="X", dependencies=["NONEXISTENT"]),
            ],
        )
        errors = validate_dag(plan)
        assert len(errors) == 1
        assert "NONEXISTENT" in errors[0]


class TestWriteScope:
    def test_no_conflicts_on_disjoint_scopes(self) -> None:
        plan = Plan(
            goal_id="G1",
            tasks=[
                TaskNode(id="A", objective="X", write_scope=["backend/auth"]),
                TaskNode(id="B", objective="Y", write_scope=["frontend/ui"]),
            ],
        )
        assert detect_write_scope_conflicts(plan) == []

    def test_conflict_on_shared_prefix(self) -> None:
        plan = Plan(
            goal_id="G1",
            tasks=[
                TaskNode(id="A", objective="X", write_scope=["backend/auth"]),
                TaskNode(id="B", objective="Y", write_scope=["backend/auth/login"]),
            ],
        )
        conflicts = detect_write_scope_conflicts(plan)
        assert len(conflicts) == 1
        assert conflicts[0][2] == "backend/auth"

    def test_non_concurrent_tasks_okay_to_share_scope(self) -> None:
        plan = Plan(
            goal_id="G1",
            tasks=[
                TaskNode(id="A", objective="X", write_scope=["backend/auth"]),
                TaskNode(id="B", objective="Y", write_scope=["backend/auth"], dependencies=["A"]),
            ],
        )
        assert detect_write_scope_conflicts(plan) == []


class TestDependencyOrder:
    def test_topological_sort(self) -> None:
        plan = Plan(
            goal_id="G1",
            tasks=[
                TaskNode(id="B", objective="Build", dependencies=["A"]),
                TaskNode(id="A", objective="Setup"),
                TaskNode(id="C", objective="Test", dependencies=["B"]),
            ],
        )
        ordered = dependency_aware_order(plan)
        ids = [t.id for t in ordered]
        assert ids.index("A") < ids.index("B") < ids.index("C")

    def test_raises_on_cycle_in_order(self) -> None:
        plan = Plan(
            goal_id="G1",
            tasks=[
                TaskNode(id="A", objective="A", dependencies=["C"]),
                TaskNode(id="B", objective="B", dependencies=["A"]),
                TaskNode(id="C", objective="C", dependencies=["B"]),
            ],
        )
        with pytest.raises(DAGError):
            dependency_aware_order(plan)


class TestWorktree:
    def test_branch_naming_convention(self) -> None:
        assert worktree_branch_name("P00-G01", "task-auth") == "atlas/P00-G01/task-auth"

    def test_directory_path(self) -> None:
        path = worktree_directory("/tmp/atlas", "G1", "T1")
        assert path == "/tmp/atlas/worktrees/G1-T1"

    def test_isolation_required_for_mutable_tasks(self) -> None:
        assert WorktreePolicy.requires_isolation(["backend/auth"])
        assert not WorktreePolicy.requires_isolation([])

    def test_coexistence_rules(self) -> None:
        assert WorktreePolicy.can_coexist(["backend/auth"], ["frontend/ui"])
        assert not WorktreePolicy.can_coexist(["backend/auth"], ["backend/auth"])
