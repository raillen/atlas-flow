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

    def test_shell_metacharacters_blocked(self) -> None:
        with pytest.raises(SecurityError):
            SecurityGuard.sanitize_shell_arg("foo; rm -rf /")

    def test_safe_arg_passed_through(self) -> None:
        result = SecurityGuard.sanitize_shell_arg("hello_world_123")
        assert "hello_world_123" in result

    def test_html_entity_escape(self) -> None:
        assert SecurityGuard.sanitize_html("<script>alert(1)</script>") == (
            "&lt;script&gt;alert(1)&lt;/script&gt;"
        )

    def test_secret_redaction(self) -> None:
        text = "token: sk-abc123 secret and password: mypass"
        redacted = SecurityGuard.redact_secrets(text)
        assert "sk-abc123" not in redacted
        assert "mypass" not in redacted
        assert "REDACTED" in redacted

    def test_git_destructive_blocked(self) -> None:
        with pytest.raises(SecurityError, match="Destructive"):
            SecurityGuard.validate_git_command(["git", "push", "origin", "main"])

        with pytest.raises(SecurityError, match="Destructive"):
            SecurityGuard.validate_git_command(["git", "reset", "--hard"])

    def test_git_safe_allowed(self) -> None:
        SecurityGuard.validate_git_command(["git", "status"])
        SecurityGuard.validate_git_command(["git", "log", "--oneline"])

    def test_unsafe_filename_blocked(self) -> None:
        assert not SecurityGuard.is_safe_filename("../escape.sh")
        assert not SecurityGuard.is_safe_filename("bad; rm")
        assert SecurityGuard.is_safe_filename("README.md")

    def test_model_output_sanitized(self) -> None:
        raw = '<div onclick="bad()">Hello</div>'
        clean = SecurityGuard.validate_model_output_for_ui(raw)
        assert "Hello" in clean
        assert "<" not in clean
