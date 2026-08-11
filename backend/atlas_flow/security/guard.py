"""Security hardening layer — input sanitization, path boundaries, permission checks (P09)."""

import re
from pathlib import Path

SHELL_DANGEROUS = re.compile(r'[;&|`$(){}\[\]<>*?!\n\r\t]')
PATH_TRAVERSAL = re.compile(r'(?:^|/)\.\.(?:/|$)')

# Applied to every piece of agent-produced text that leaves the runner, so a
# token an agent echoed never reaches a log, a transcript or a client.
SECRET_PATTERNS = [
    r'(?:sk|api[_-]?key|token|secret|password)\s*[:=]\s*[^\s]+',
    r'Bearer\s+[A-Za-z0-9\-._~+/]+=*',
    r'\bgh[pousr]_[A-Za-z0-9]{16,}',
    r'\bsk-[A-Za-z0-9]{16,}',
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
]

# Publishing, history rewriting, and discarding work the user never handed
# over. Committing and merging are deliberately absent: they are the job, and a
# worktree that cannot commit cannot integrate anything.
FORBIDDEN_GIT_SUBCOMMANDS = frozenset({
    "push", "reset", "rebase", "filter-branch", "filter-repo",
    "clean", "gc", "prune", "reflog",
})


class SecurityError(Exception):
    """Raised when a security boundary is violated."""


class SecurityGuard:
    """Validates inputs at trust boundaries."""

    @staticmethod
    def validate_path(repo_root: Path, target: str | Path) -> Path:
        """Ensure target is inside repo_root. Blocks traversal."""
        resolved = (repo_root / target).resolve()
        try:
            resolved.relative_to(repo_root.resolve())
        except ValueError as exc:
            raise SecurityError(
                f"Path traversal blocked: {target} escapes {repo_root}"
            ) from exc
        return resolved

    @staticmethod
    def redact_secrets(text: str, patterns: list[str] | None = None) -> str:
        """Remove known secret patterns from text before logging/storing.

        Extra patterns are added to the defaults rather than replacing them: a
        project that wants to catch one more shape of secret should not have to
        restate the ones already covered, and silently losing the defaults is
        exactly the mistake that turns a redaction list into a leak.
        """
        for pat in SECRET_PATTERNS + list(patterns or []):
            text = re.sub(pat, '[REDACTED]', text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def validate_git_command(args: list[str]) -> None:
        """Refuse git operations Atlas Flow must never perform.

        Committing and merging are the job — a worktree that cannot commit
        cannot integrate anything — so they are allowed. What is refused is
        everything that reaches outside the local repository or destroys work
        the user has not handed over: publishing, rewriting history, and
        discarding uncommitted state.
        """
        # `git worktree prune` is as forbidden as `git prune`, so every word is
        # checked rather than only the first: a subcommand hidden behind
        # another verb is still the operation being refused.
        for word in args:
            if word.lower() in FORBIDDEN_GIT_SUBCOMMANDS:
                raise SecurityError(
                    f"git {word} is never performed by Atlas Flow: {' '.join(args)}"
                )

    @staticmethod
    def is_safe_filename(name: str) -> bool:
        """Ensure a filename does not attempt traversal or contain shell chars."""
        if PATH_TRAVERSAL.search(name):
            return False
        if SHELL_DANGEROUS.search(name):
            return False
        return bool(name) and not name.startswith(".")
