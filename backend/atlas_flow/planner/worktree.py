"""Worktree isolation strategy (P05)."""

from __future__ import annotations


def worktree_branch_name(goal_id: str, task_id: str) -> str:
    """Atlas Flow worktree naming convention (ADR docs)."""
    return f"atlas/{goal_id}/{task_id}"


def worktree_directory(base: str, goal_id: str, task_id: str) -> str:
    return f"{base}/worktrees/{goal_id}-{task_id}"


class WorktreePolicy:
    """Determines when to isolate and when to integrate."""

    @staticmethod
    def requires_isolation(task_write_scope: list[str]) -> bool:
        return len(task_write_scope) > 0

    @staticmethod
    def can_coexist(scope_a: list[str], scope_b: list[str]) -> bool:
        for pa in scope_a:
            for pb in scope_b:
                parts_a = pa.strip("/").split("/")
                parts_b = pb.strip("/").split("/")
                common = 0
                for ca, cb in zip(parts_a, parts_b, strict=False):
                    if ca == cb:
                        common += 1
                    else:
                        break
                if common > 0 and common == min(len(parts_a), len(parts_b)):
                    return False
        return True
