"""P05 worktree isolation against a real git repository."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from atlas_flow.planner.worktree import (
    GitError,
    WorktreeManager,
    WorktreePolicy,
    partition_parallel_safe,
    run_git,
    worktree_branch_name,
)


@pytest_asyncio.fixture
async def repo(tmp_path: Path) -> AsyncIterator[Path]:
    """A small repository with one commit on `main`."""
    root = tmp_path / "repo"
    root.mkdir()
    await run_git(root, "init", "--initial-branch=main")
    await run_git(root, "config", "user.email", "test@atlas-flow.invalid")
    await run_git(root, "config", "user.name", "Atlas Flow Test")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    (root / "backend").mkdir()
    (root / "backend" / "app.py").write_text("value = 1\n", encoding="utf-8")
    await run_git(root, "add", "-A")
    await run_git(root, "commit", "-m", "initial")
    yield root


@pytest.mark.asyncio
class TestWorktreeLifecycle:
    async def test_create_produces_a_real_checkout_on_its_own_branch(
        self, repo: Path
    ) -> None:
        manager = WorktreeManager(repo)
        worktree = await manager.create("P05-G01", "task-a")

        assert worktree.path.is_dir()
        assert (worktree.path / "README.md").read_text(encoding="utf-8") == "base\n"
        assert worktree.branch == worktree_branch_name("P05-G01", "task-a")

        branch = (
            await run_git(worktree.path, "rev-parse", "--abbrev-ref", "HEAD")
        ).strip()
        assert branch == worktree.branch

        assert worktree.path.resolve() in [p.resolve() for p in await manager.list_paths()]

    async def test_parallel_worktrees_do_not_share_a_tree(self, repo: Path) -> None:
        manager = WorktreeManager(repo)
        first = await manager.create("P05-G01", "task-a")
        second = await manager.create("P05-G01", "task-b")

        (first.path / "one.txt").write_text("from a\n", encoding="utf-8")
        (second.path / "two.txt").write_text("from b\n", encoding="utf-8")

        assert not (second.path / "one.txt").exists()
        assert not (first.path / "two.txt").exists()
        assert not (repo / "one.txt").exists()

    async def test_state_directory_stays_invisible_to_git(self, repo: Path) -> None:
        """Atlas Flow's own bookkeeping must not dirty the user's repository."""
        manager = WorktreeManager(repo)
        await manager.create("P05-G01", "task-a")

        status = await run_git(repo, "status", "--porcelain")
        assert status.strip() == ""
        assert not await manager.is_dirty(repo)

    async def test_remove_refuses_to_discard_uncommitted_work(self, repo: Path) -> None:
        manager = WorktreeManager(repo)
        worktree = await manager.create("P05-G01", "task-a")
        (worktree.path / "scratch.txt").write_text("unsaved\n", encoding="utf-8")

        with pytest.raises(GitError):
            await manager.remove(worktree)
        assert worktree.path.is_dir()

        await manager.remove(worktree, force=True)
        assert not worktree.path.exists()


@pytest.mark.asyncio
class TestIntegration:
    async def test_clean_task_branch_merges_into_main(self, repo: Path) -> None:
        manager = WorktreeManager(repo)
        worktree = await manager.create("P05-G01", "task-a")
        (worktree.path / "feature.txt").write_text("done\n", encoding="utf-8")
        assert await manager.commit_all(worktree, "task-a: add feature")

        result = await manager.integrate(worktree, "main")

        assert result.integrated
        assert not result.has_conflicts
        assert (repo / "feature.txt").read_text(encoding="utf-8") == "done\n"

    async def test_conflicting_branch_is_reported_not_forced(self, repo: Path) -> None:
        manager = WorktreeManager(repo)
        worktree = await manager.create("P05-G01", "task-a")

        (worktree.path / "backend" / "app.py").write_text("value = 2\n", encoding="utf-8")
        await manager.commit_all(worktree, "task-a: set 2")

        (repo / "backend" / "app.py").write_text("value = 3\n", encoding="utf-8")
        await run_git(repo, "add", "-A")
        await run_git(repo, "commit", "-m", "main: set 3")

        result = await manager.integrate(worktree, "main")

        assert not result.integrated
        assert result.conflicts == ["backend/app.py"]
        assert "conflicting path" in result.reason
        # The refusal must leave main exactly as it was.
        assert (repo / "backend" / "app.py").read_text(encoding="utf-8") == "value = 3\n"
        assert not (await manager.is_dirty(repo))

    async def test_integration_refuses_when_target_has_uncommitted_changes(
        self, repo: Path
    ) -> None:
        manager = WorktreeManager(repo)
        worktree = await manager.create("P05-G01", "task-a")
        (worktree.path / "feature.txt").write_text("done\n", encoding="utf-8")
        await manager.commit_all(worktree, "task-a: add feature")

        (repo / "README.md").write_text("edited by the user\n", encoding="utf-8")

        result = await manager.integrate(worktree, "main")

        assert not result.integrated
        assert "uncommitted changes" in result.reason
        assert (repo / "README.md").read_text(encoding="utf-8") == "edited by the user\n"

    async def test_task_that_produced_nothing_is_not_committed(self, repo: Path) -> None:
        manager = WorktreeManager(repo)
        worktree = await manager.create("P05-G01", "task-a")
        assert await manager.commit_all(worktree, "task-a: nothing") is False


class TestScopePartitioning:
    def test_overlapping_scopes_are_not_parallel_safe(self) -> None:
        assert not WorktreePolicy.can_coexist(["backend"], ["backend/auth"])
        assert WorktreePolicy.can_coexist(["backend"], ["apps/desktop"])

    def test_partition_separates_overlapping_tasks(self) -> None:
        batches = partition_parallel_safe(
            {
                "t1": ["backend/auth"],
                "t2": ["apps/desktop"],
                "t3": ["backend/auth/session"],
            }
        )
        assert ["t1", "t2"] in batches
        assert ["t3"] in batches

    def test_task_without_write_scope_needs_no_isolation(self) -> None:
        assert not WorktreePolicy.requires_isolation([])
        assert WorktreePolicy.requires_isolation(["docs"])
