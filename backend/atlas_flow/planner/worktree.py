"""Worktree isolation strategy and git execution (P05).

Mutable parallel tasks each get a dedicated worktree and branch so no two of
them can silently write to the same tree. Integration happens after a task's
gates pass, and a conflict is always reported explicitly rather than resolved
by overwriting one side (docs/01-architecture/GIT_WORKTREES.md).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from atlas_flow.workspace import ensure_private_dir


class GitError(Exception):
    """A git command failed."""

    def __init__(self, args: list[str], returncode: int, stderr: str) -> None:
        self.args_run = args
        self.returncode = returncode
        self.stderr = stderr.strip()
        super().__init__(f"git {' '.join(args)} failed ({returncode}): {self.stderr}")


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
        """False when either scope contains the other, so they may overlap."""
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


@dataclass(frozen=True)
class Worktree:
    """A checked-out worktree owned by one task."""

    goal_id: str
    task_id: str
    branch: str
    path: Path


@dataclass
class IntegrationResult:
    """Outcome of merging a task branch back into its target."""

    branch: str
    target: str
    integrated: bool
    conflicts: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


async def run_git(repo: Path, *args: str) -> str:
    """Run a git command in `repo` and return stdout, raising on failure."""
    stdout, stderr, code = await _run_git_raw(repo, *args)
    if code != 0:
        raise GitError(list(args), code, stderr)
    return stdout


async def _run_git_raw(repo: Path, *args: str) -> tuple[str, str, int]:
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(repo),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    raw_out, raw_err = await process.communicate()
    return (
        raw_out.decode("utf-8", errors="replace"),
        raw_err.decode("utf-8", errors="replace"),
        process.returncode or 0,
    )


class WorktreeManager:
    """Creates, lists, integrates and removes task worktrees."""

    def __init__(self, repo_root: Path, base: Path | None = None) -> None:
        self.repo_root = repo_root
        self.base = base or repo_root / ".atlas-flow"
        # Tasks run in parallel in isolated worktrees, but they all integrate
        # into the same branch. Two concurrent merges race on HEAD and one of
        # them dies with "cannot lock ref"; integration is serialized instead.
        self._integration_lock = asyncio.Lock()

    async def create(self, goal_id: str, task_id: str, start_point: str = "HEAD") -> Worktree:
        branch = worktree_branch_name(goal_id, task_id)
        path = Path(worktree_directory(str(self.base), goal_id, task_id))
        ensure_private_dir(self.base)
        path.parent.mkdir(parents=True, exist_ok=True)
        await run_git(
            self.repo_root, "worktree", "add", "-b", branch, str(path), start_point
        )
        return Worktree(goal_id=goal_id, task_id=task_id, branch=branch, path=path)

    async def list_paths(self) -> list[Path]:
        output = await run_git(self.repo_root, "worktree", "list", "--porcelain")
        return [
            Path(line.removeprefix("worktree ").strip())
            for line in output.splitlines()
            if line.startswith("worktree ")
        ]

    async def remove(self, worktree: Worktree, force: bool = False) -> None:
        """Remove a worktree. Uncommitted work blocks removal unless forced.

        Failed or cancelled worktrees are meant to survive for inspection, so
        the caller decides when work may be discarded.
        """
        args = ["worktree", "remove", str(worktree.path)]
        if force:
            args.append("--force")
        await run_git(self.repo_root, *args)

    async def is_dirty(self, repo: Path) -> bool:
        return bool((await run_git(repo, "status", "--porcelain")).strip())

    async def commit_all(self, worktree: Worktree, message: str) -> bool:
        """Commit everything a task produced. Returns False if it produced nothing."""
        if not await self.is_dirty(worktree.path):
            return False
        await run_git(worktree.path, "add", "-A")
        await run_git(worktree.path, "commit", "-m", message)
        return True

    async def detect_conflicts(self, branch: str, target: str) -> list[str]:
        """List paths that would conflict, without touching any working tree.

        `git merge-tree --write-tree` performs the merge in the object database
        only, so conflict detection never leaves the target checkout in a
        half-merged state that a user would have to clean up.
        """
        stdout, stderr, code = await _run_git_raw(
            self.repo_root, "merge-tree", "--write-tree", "--name-only", target, branch
        )
        if code == 0:
            return []
        if code != 1:
            raise GitError(["merge-tree", target, branch], code, stderr)

        # On conflict the first line is the tree oid, then the conflicted paths
        # up to a blank line, then human-readable conflict messages.
        lines = stdout.splitlines()[1:]
        conflicts: list[str] = []
        for line in lines:
            if not line.strip():
                break
            conflicts.append(line.strip())
        return conflicts

    async def integrate(self, worktree: Worktree, target: str) -> IntegrationResult:
        """Merge a task branch into `target`, refusing anything ambiguous.

        Integration is refused — never forced — when the target tree has
        uncommitted changes or when the merge would conflict. Both cases need a
        human decision, and forcing either one would overwrite work that Atlas
        Flow did not create.
        """
        async with self._integration_lock:
            return await self._integrate_locked(worktree, target)

    async def _integrate_locked(self, worktree: Worktree, target: str) -> IntegrationResult:
        result = IntegrationResult(branch=worktree.branch, target=target, integrated=False)

        if await self.is_dirty(self.repo_root):
            result.reason = (
                f"Target checkout {self.repo_root} has uncommitted changes; "
                "integration would risk overwriting unrelated user work."
            )
            return result

        conflicts = await self.detect_conflicts(worktree.branch, target)
        if conflicts:
            result.conflicts = conflicts
            result.reason = (
                f"{len(conflicts)} conflicting path(s) between "
                f"{worktree.branch} and {target}; resolve them explicitly."
            )
            return result

        current = (await run_git(self.repo_root, "rev-parse", "--abbrev-ref", "HEAD")).strip()
        if current != target:
            await run_git(self.repo_root, "checkout", target)
        await run_git(
            self.repo_root,
            "merge",
            "--no-ff",
            "-m",
            f"Integrate {worktree.branch}",
            worktree.branch,
        )

        result.integrated = True
        result.reason = f"Merged {worktree.branch} into {target}."
        return result


def partition_parallel_safe(scopes: dict[str, list[str]]) -> list[list[str]]:
    """Group task ids into batches whose write scopes cannot overlap.

    Tasks in the same batch are safe to run in parallel; a task that overlaps
    an earlier one starts a new batch rather than racing it.
    """
    batches: list[list[str]] = []
    for task_id, scope in scopes.items():
        for batch in batches:
            if all(
                WorktreePolicy.can_coexist(scope, scopes[other]) for other in batch
            ):
                batch.append(task_id)
                break
        else:
            batches.append([task_id])
    return batches
