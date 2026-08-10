"""Local workspace directories for operational state.

Atlas Flow keeps its database and task worktrees inside the project it is
working on, which means those files sit in someone else's repository. They are
operational, never canonical (ADR-009), so git must not see them at all: an
untracked state directory would show up in the user's `git status` and would
make Atlas Flow's own dirty-tree checks fire on its own bookkeeping.
"""

from __future__ import annotations

from pathlib import Path

_SELF_IGNORE = "# Managed by Atlas Flow. Operational state, never committed.\n*\n"


def ensure_private_dir(path: Path) -> Path:
    """Create `path` and make git ignore everything inside it, including itself."""
    path.mkdir(parents=True, exist_ok=True)
    marker = path / ".gitignore"
    if not marker.exists():
        marker.write_text(_SELF_IGNORE, encoding="utf-8")
    return path
