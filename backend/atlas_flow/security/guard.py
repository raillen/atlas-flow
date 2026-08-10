"""Security hardening layer — input sanitization, path boundaries, permission checks (P09)."""

import re
import shlex
from pathlib import Path

SHELL_DANGEROUS = re.compile(r'[;&|`$(){}\[\]<>*?!\n\r\t]')
PATH_TRAVERSAL = re.compile(r'(?:^|/)\.\.(?:/|$)')


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
    def sanitize_shell_arg(value: str) -> str:
        """Detect dangerous shell metacharacters in tool arguments."""
        if SHELL_DANGEROUS.search(value):
            raise SecurityError(
                f"Shell metacharacters detected in argument: {value!r}"
            )
        return shlex.quote(value)

    @staticmethod
    def sanitize_html(value: str) -> str:
        """Escape HTML entities to prevent injection in UI/transcripts."""
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    @staticmethod
    def redact_secrets(text: str, patterns: list[str] | None = None) -> str:
        """Remove known secret patterns from text before logging/storing."""
        default_patterns = [
            r'(?:sk|api[_-]?key|token|secret|password)\s*[:=]\s*[^\s]+',
            r'Bearer\s+[A-Za-z0-9\-._~+/]+=*',
        ]
        for pat in (patterns or default_patterns):
            text = re.sub(pat, '[REDACTED]', text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def validate_git_command(args: list[str]) -> None:
        """Block destructive git commands in automated runners."""
        destructive = {"push", "force", "--force", "reset", "rebase", "commit", "merge"}
        for arg in args:
            arg_lower = arg.lstrip("-").lower()
            if arg in destructive or arg_lower in destructive:
                raise SecurityError(
                    f"Destructive git operation blocked: {' '.join(args)}"
                )

    @staticmethod
    def validate_model_output_for_ui(text: str) -> str:
        """Sanitize model output before rendering in UI."""
        return SecurityGuard.sanitize_html(text)

    @staticmethod
    def is_safe_filename(name: str) -> bool:
        """Ensure a filename does not attempt traversal or contain shell chars."""
        if PATH_TRAVERSAL.search(name):
            return False
        if SHELL_DANGEROUS.search(name):
            return False
        return bool(name) and not name.startswith(".")
