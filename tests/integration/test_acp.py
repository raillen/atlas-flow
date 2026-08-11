"""P04 ACP client against a real agent process."""

import json
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from atlas_flow.acp.client import AcpClient, PermissionRequest, deny_all
from atlas_flow.acp.events import NormalizedUpdate, UpdateKind
from atlas_flow.acp.protocol import AcpError, AcpRemoteError
from atlas_flow.harness.engine import Harness
from atlas_flow.harness.runner import RunnerCapability, RunnerConfig
from atlas_flow.mcp.registry import McpRegistry
from atlas_flow.runners.acp import AcpRunner, allow_read_only

AGENT = Path(__file__).resolve().parents[1] / "fixtures" / "acp_agent.py"


def agent_command(mode: str = "basic") -> list[str]:
    return [sys.executable, str(AGENT)]


@pytest_asyncio.fixture
async def client_factory() -> AsyncIterator[list[AcpClient]]:
    """Tracks every client opened by a test so none leaks a subprocess."""
    opened: list[AcpClient] = []
    yield opened
    for client in opened:
        await client.close()


async def connect(
    opened: list[AcpClient], mode: str = "basic", **kwargs: object
) -> AcpClient:
    os.environ["ACP_FIXTURE_MODE"] = mode
    client = AcpClient(**kwargs)  # type: ignore[arg-type]
    opened.append(client)
    await client.start(agent_command(mode))
    return client


@pytest.mark.asyncio
class TestSessionLifecycle:
    async def test_initialize_negotiates_capabilities(
        self, client_factory: list[AcpClient]
    ) -> None:
        client = await connect(client_factory)
        capabilities = await client.initialize()

        assert capabilities.protocol_version == 1
        assert capabilities.supports("loadSession")
        assert capabilities.prompt_capabilities["image"] is True
        assert capabilities.prompt_capabilities["audio"] is False

    async def test_session_new_then_prompt(self, client_factory: list[AcpClient]) -> None:
        client = await connect(client_factory)
        await client.initialize()
        session_id = await client.new_session(".")

        assert session_id.startswith("fixture-session-")

        result = await client.prompt("do the work", timeout=10)
        assert result.completed
        assert result.stop_reason == "end_turn"
        assert result.text == "work done"
        assert len(result.updates) == 1

    async def test_prompt_before_session_is_refused(
        self, client_factory: list[AcpClient]
    ) -> None:
        client = await connect(client_factory)
        await client.initialize()
        with pytest.raises(AcpError, match="before a session"):
            await client.prompt("too early")

    async def test_resume_is_skipped_when_the_agent_cannot_do_it(
        self, client_factory: list[AcpClient]
    ) -> None:
        """An unsupported optional capability degrades, it does not fail."""
        client = await connect(client_factory, mode="no_session")
        capabilities = await client.initialize()

        assert not capabilities.supports("loadSession")
        assert await client.load_session("whatever", ".") is False

    async def test_incompatible_protocol_version_is_rejected(
        self, client_factory: list[AcpClient]
    ) -> None:
        client = await connect(client_factory, mode="old")
        with pytest.raises(AcpError, match="ACP v99"):
            await client.initialize()

    async def test_agent_error_surfaces_as_a_remote_error(
        self, client_factory: list[AcpClient]
    ) -> None:
        client = await connect(client_factory, mode="error")
        await client.initialize()
        await client.new_session(".")

        with pytest.raises(AcpRemoteError, match="agent refused the prompt"):
            await client.prompt("go", timeout=10)

    async def test_non_json_output_does_not_break_the_session(
        self, client_factory: list[AcpClient]
    ) -> None:
        """Agents write diagnostics to stdout; that must not kill the session."""
        client = await connect(client_factory, mode="noisy")
        await client.initialize()
        await client.new_session(".")

        result = await client.prompt("go", timeout=10)
        assert result.completed

    async def test_missing_agent_binary_is_reported_clearly(self) -> None:
        client = AcpClient()
        with pytest.raises(AcpError, match="not found"):
            await client.start(["definitely-not-a-real-agent-binary"])


@pytest.mark.asyncio
class TestPermissions:
    async def test_permission_request_is_surfaced_and_denied_by_default(
        self, client_factory: list[AcpClient]
    ) -> None:
        client = await connect(client_factory, mode="permission")
        await client.initialize()
        await client.new_session(".")

        result = await client.prompt("write a file", timeout=10)

        assert len(result.permissions_requested) == 1
        assert result.permissions_requested[0].tool_name == "write_file"
        assert result.permissions_denied == ["write_file"]
        assert result.text == "blocked without permission"

    async def test_granting_permission_lets_the_agent_proceed(
        self, client_factory: list[AcpClient]
    ) -> None:
        async def allow_everything(request: PermissionRequest) -> bool:
            return True

        client = await connect(
            client_factory, mode="permission", permission_policy=allow_everything
        )
        await client.initialize()
        await client.new_session(".")

        result = await client.prompt("write a file", timeout=10)

        assert result.permissions_denied == []
        assert result.text == "work done"

    async def test_read_only_policy_refuses_an_edit(
        self, client_factory: list[AcpClient]
    ) -> None:
        client = await connect(
            client_factory, mode="permission", permission_policy=allow_read_only
        )
        await client.initialize()
        await client.new_session(".")

        result = await client.prompt("write a file", timeout=10)
        assert result.permissions_denied == ["write_file"]

    async def test_default_policy_denies(self) -> None:
        request = PermissionRequest(session_id="s", tool_name="rm -rf")
        assert await deny_all(request) is False


@pytest.mark.asyncio
class TestAcpRunner:
    async def test_runner_executes_a_task_through_the_agent(self) -> None:
        os.environ["ACP_FIXTURE_MODE"] = "basic"
        runner = AcpRunner(agent_command(), name="acp-test", cwd=".")

        result = await runner.run("task-1", "do the work", RunnerConfig(model="any"))

        assert result.success
        assert result.output == "work done"
        assert result.evidence["stop_reason"] == "end_turn"

    async def test_runner_reports_denied_permissions_as_failure(self) -> None:
        os.environ["ACP_FIXTURE_MODE"] = "permission"
        runner = AcpRunner(agent_command(), name="acp-test", cwd=".")

        result = await runner.run("task-1", "write a file", RunnerConfig(model="any"))

        assert not result.success
        assert "write_file" in result.error

    async def test_runner_advertises_permissions_capability(self) -> None:
        runner = AcpRunner(agent_command(), name="acp-test")
        assert runner.has_capability(RunnerCapability.PERMISSIONS)
        assert runner.has_capability(RunnerCapability.AGENT_SESSION)

    async def test_harness_selects_the_acp_runner_for_permission_work(self) -> None:
        from atlas_flow.execution.persistence import Persistence

        db = Persistence(":memory:")
        await db.initialize()
        try:
            harness = Harness(db)
            harness.register(AcpRunner(agent_command(), name="acp"))
            chosen = harness.select_runner(
                [RunnerCapability.PERMISSIONS, RunnerCapability.STREAMING]
            )
            assert chosen.name == "acp"
        finally:
            await db.close()

    async def test_missing_agent_is_a_failed_result_not_a_crash(self) -> None:
        runner = AcpRunner(["definitely-not-a-real-agent-binary"], name="acp-missing")
        result = await runner.run("task-1", "go", RunnerConfig(model="any"))

        assert not result.success
        assert "not found" in result.error


@pytest.mark.asyncio
class TestMcpForwarding:
    """The agent can only reach a server the client handed it at session/new."""

    def _registry(self, tmp_path: Path, body: str) -> McpRegistry:
        target = tmp_path / "mcp-servers.yaml"
        target.write_text(body, encoding="utf-8")
        return McpRegistry.from_file(target)

    async def test_declared_servers_reach_the_agent(self, tmp_path: Path) -> None:
        registry = self._registry(
            tmp_path,
            "servers:\n"
            "  - name: docs\n"
            "    command: mcp-docs\n"
            "    args: ['--stdio']\n"
            "    read_only: true\n",
        )
        os.environ["ACP_FIXTURE_MODE"] = "echo_mcp"
        runner = AcpRunner(agent_command(), name="acp-mcp", mcp=registry)

        result = await runner.run(
            "task-1", "go", RunnerConfig(model="any", role="core-implementer")
        )

        assert result.success
        assert json.loads(result.output) == [
            {
                "name": "docs",
                "command": "mcp-docs",
                "args": ["--stdio"],
                "env": [],
            }
        ]
        assert "forwarded: docs" in result.evidence["mcp"]

    async def test_a_planning_role_never_receives_a_mutating_server(
        self, tmp_path: Path
    ) -> None:
        registry = self._registry(
            tmp_path,
            "servers:\n"
            "  - name: deploy\n"
            "    command: mcp-deploy\n"
            "    read_only: false\n",
        )
        os.environ["ACP_FIXTURE_MODE"] = "echo_mcp"
        runner = AcpRunner(agent_command(), name="acp-mcp", mcp=registry)

        result = await runner.run(
            "task-1", "plan", RunnerConfig(model="any", role="goal-planner")
        )

        assert result.success
        assert json.loads(result.output) == []
        assert "forwarded: none" in result.evidence["mcp"]

    async def test_without_a_registry_no_servers_are_forwarded(self) -> None:
        os.environ["ACP_FIXTURE_MODE"] = "echo_mcp"
        runner = AcpRunner(agent_command(), name="acp-plain")

        result = await runner.run(
            "task-1", "go", RunnerConfig(model="any", role="core-implementer")
        )

        assert json.loads(result.output) == []
        assert result.evidence["mcp"] == "MCP forwarding is disabled"


@pytest.mark.asyncio
class TestTerminalAndFileEvents:
    """What the agent runs and changes reaches the client as typed events."""

    async def test_a_run_streams_terminal_and_file_events_in_order(self) -> None:
        seen: list[tuple[str, NormalizedUpdate]] = []

        async def sink(task_id: str, event: NormalizedUpdate) -> None:
            seen.append((task_id, event))

        os.environ["ACP_FIXTURE_MODE"] = "tooling"
        runner = AcpRunner(agent_command(), name="acp-tooling", on_event=sink)

        result = await runner.run("task-7", "go", RunnerConfig(model="any"))

        assert result.success
        assert [event.kind for _, event in seen] == [
            UpdateKind.TERMINAL, UpdateKind.FILE, UpdateKind.MESSAGE
        ]
        assert {task_id for task_id, _ in seen} == {"task-7"}

    async def test_terminal_output_lands_in_the_transcript(self) -> None:
        os.environ["ACP_FIXTURE_MODE"] = "tooling"
        runner = AcpRunner(agent_command(), name="acp-tooling")

        result = await runner.run("task-7", "go", RunnerConfig(model="any"))

        assert "work done" in result.transcript
        assert "2 passed" in result.transcript
        # The agent's answer is what the task produced; terminal output is
        # context, so the two are not silently interleaved.
        assert "--- terminal ---" in result.transcript

    async def test_changed_files_are_recorded_as_evidence(self) -> None:
        os.environ["ACP_FIXTURE_MODE"] = "tooling"
        runner = AcpRunner(agent_command(), name="acp-tooling")

        result = await runner.run("task-7", "go", RunnerConfig(model="any"))

        assert result.evidence["files_changed"] == "backend/auth.py"

    async def test_an_unrecognized_update_is_kept_but_not_published(self) -> None:
        """It stays in the raw updates for debugging; nothing downstream sees it."""
        os.environ["ACP_FIXTURE_MODE"] = "tooling"
        client = AcpClient()
        try:
            await client.start(agent_command())
            await client.initialize()
            await client.new_session(".")
            result = await client.prompt("go")
        finally:
            await client.close()

        kinds = [str(u.get("sessionUpdate")) for u in result.updates]
        assert "something_new_this_client_never_heard_of" in kinds
        assert len(result.events) == len(result.updates) - 1
