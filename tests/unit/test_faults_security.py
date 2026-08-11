"""P09 Fault injection and security tests."""

from pathlib import Path

import pytest

from atlas_flow.execution.faults import FaultInjector, FaultKind, FaultPoint
from atlas_flow.security.guard import SecurityError, SecurityGuard


class TestFaultInjection:
    def test_single_trigger(self) -> None:
        injector = FaultInjector()
        injector.register("task-1", FaultPoint(kind=FaultKind.TIMEOUT, target="task-1"))
        assert injector.inject("task-1", FaultKind.TIMEOUT)
        assert injector.triggered_count(FaultKind.TIMEOUT) == 1

    def test_counted_trigger(self) -> None:
        injector = FaultInjector()
        injector.register(
            "task-2",
            FaultPoint(kind=FaultKind.DISCONNECT, target="task-2", trigger_count=2),
        )
        assert not injector.inject("task-2", FaultKind.DISCONNECT)
        assert injector.inject("task-2", FaultKind.DISCONNECT)
        assert injector.triggered_count() == 1

    def test_disabled_point(self) -> None:
        injector = FaultInjector()
        injector.register(
            "task-3",
            FaultPoint(kind=FaultKind.PROCESS_KILL, target="task-3", enabled=False),
        )
        assert not injector.inject("task-3", FaultKind.PROCESS_KILL)
        assert injector.triggered_count() == 0

    def test_reset_clears_all(self) -> None:
        injector = FaultInjector()
        injector.register("x", FaultPoint(kind=FaultKind.MALFORMED_OUTPUT, target="x"))
        injector.inject("x", FaultKind.MALFORMED_OUTPUT)
        injector.reset()
        assert injector.triggered_count() == 0

    def test_no_match_when_kind_differs(self) -> None:
        injector = FaultInjector()
        injector.register("task", FaultPoint(kind=FaultKind.GIT_CONFLICT, target="task"))
        assert not injector.inject("task", FaultKind.TIMEOUT)


class TestSecurityGuard:
    def test_path_traversal_blocked(self) -> None:
        root = Path("/safe/repo")
        with pytest.raises(SecurityError, match="traversal"):
            SecurityGuard.validate_path(root, "../../etc/passwd")

    def test_valid_path_allowed(self) -> None:
        root = Path("/safe/repo")
        resolved = SecurityGuard.validate_path(root, "src/main.py")
        assert resolved == Path("/safe/repo/src/main.py")

    def test_secret_redaction(self) -> None:
        text = "token: sk-abc123 secret and password: mypass"
        redacted = SecurityGuard.redact_secrets(text)
        assert "sk-abc123" not in redacted
        assert "mypass" not in redacted
        assert "REDACTED" in redacted

    def test_bare_credentials_are_redacted_without_a_label(self) -> None:
        """A token pasted into output rarely arrives with "token:" in front."""
        text = "cloning with ghp_0123456789abcdefghij and sk-ABCDEFGHIJKLMNOPQR"
        redacted = SecurityGuard.redact_secrets(text)

        assert "ghp_0123456789abcdefghij" not in redacted
        assert "sk-ABCDEFGHIJKLMNOPQR" not in redacted

    def test_a_private_key_header_is_redacted(self) -> None:
        redacted = SecurityGuard.redact_secrets("-----BEGIN RSA PRIVATE KEY-----")
        assert "PRIVATE KEY" not in redacted

    def test_custom_patterns_add_to_the_defaults_rather_than_replacing_them(
        self,
    ) -> None:
        """Replacing them is how a redaction list quietly becomes a leak."""
        redacted = SecurityGuard.redact_secrets(
            "internal-id-4242 and token: abc123", patterns=[r"internal-id-\d+"]
        )

        assert "internal-id-4242" not in redacted
        assert "abc123" not in redacted

    def test_ordinary_text_survives_redaction(self) -> None:
        assert SecurityGuard.redact_secrets("2 passed in 4.6s") == "2 passed in 4.6s"

    def test_publishing_and_rewriting_are_refused(self) -> None:
        for args in (
            ["git", "push", "origin", "main"],
            ["git", "reset", "--hard"],
            ["git", "rebase", "main"],
            ["git", "clean", "-fd"],
            ["git", "filter-branch"],
            ["git", "worktree", "prune"],
        ):
            with pytest.raises(SecurityError, match="never performed"):
                SecurityGuard.validate_git_command(args)

    def test_committing_and_merging_are_allowed(self) -> None:
        """They are the job: a worktree that cannot commit cannot integrate."""
        SecurityGuard.validate_git_command(["commit", "-m", "work"])
        SecurityGuard.validate_git_command(["merge", "--no-ff", "branch"])
        SecurityGuard.validate_git_command(["worktree", "remove", "--force", "path"])
        SecurityGuard.validate_git_command(["status", "--porcelain"])

    def test_unsafe_filename_blocked(self) -> None:
        assert not SecurityGuard.is_safe_filename("../escape.sh")
        assert not SecurityGuard.is_safe_filename("bad; rm")
        assert SecurityGuard.is_safe_filename("README.md")

