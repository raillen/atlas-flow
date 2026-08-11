"""ACP runner — preferred transport between Atlas Harness and coding agents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from atlas_flow.acp.client import AcpClient, PermissionPolicy, PermissionRequest
from atlas_flow.acp.events import NormalizedUpdate
from atlas_flow.acp.protocol import AcpError
from atlas_flow.harness.runner import (
    Runner,
    RunnerCapability,
    RunnerConfig,
    RunnerResult,
)
from atlas_flow.mcp.registry import McpRegistry
from atlas_flow.security.guard import SecurityGuard

# The task id travels with the event so a consumer can attribute terminal
# output to the task that produced it without threading state of its own.
TaskEventListener = Callable[[str, NormalizedUpdate], Awaitable[None]]


class AcpRunner(Runner):
    """Runs a task through an ACP agent subprocess.

    Capabilities are advertised up front from what the transport can do; the
    ones that depend on the agent are confirmed after initialize, so
    negotiation reflects the agent in front of us rather than the protocol in
    the abstract.
    """

    def __init__(
        self,
        command: list[str],
        name: str = "acp",
        cwd: str | None = None,
        permission_policy: PermissionPolicy | None = None,
        mcp: McpRegistry | None = None,
        on_event: TaskEventListener | None = None,
    ) -> None:
        super().__init__(
            name,
            [
                RunnerCapability.AGENT_SESSION,
                RunnerCapability.CANCELLATION,
                RunnerCapability.PERMISSIONS,
                RunnerCapability.STREAMING,
                RunnerCapability.TRANSCRIPT,
                RunnerCapability.RESULT_CAPTURE,
            ],
        )
        self.command = command
        self.cwd = cwd
        self.permission_policy = permission_policy
        self.mcp = mcp or McpRegistry(enabled=False)
        self.on_event = on_event
        self._clients: dict[str, AcpClient] = {}
        if RunnerCapability.TOOL_ACCESS not in self.capabilities and self.mcp.servers:
            self.capabilities.add(RunnerCapability.TOOL_ACCESS)

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        async def publish(event: NormalizedUpdate) -> None:
            if self.on_event is not None:
                await self.on_event(task_id, event)

        client = AcpClient(
            permission_policy=self.permission_policy,
            on_event=publish if self.on_event is not None else None,
        )
        self._clients[task_id] = client

        try:
            await client.start(self.command, cwd=self.cwd)
            await client.initialize()
            self._reconcile_capabilities(client)
            # Which servers this role may reach is decided here, not by the
            # agent: an agent can only use a tool the client handed it.
            await client.new_session(
                self.cwd or ".", self.mcp.acp_servers(config.role)
            )

            result = await client.prompt(prompt, timeout=config.timeout_seconds)
        except AcpError as exc:
            return RunnerResult(task_id=task_id, success=False, error=str(exc))
        finally:
            await client.close()
            self._clients.pop(task_id, None)

        denied = ""
        if result.permissions_denied:
            denied = (
                "Denied permission for: " + ", ".join(sorted(set(result.permissions_denied)))
            )

        text = SecurityGuard.redact_secrets(result.text)
        return RunnerResult(
            task_id=task_id,
            success=result.completed and not result.permissions_denied,
            output=text,
            error=denied if not result.completed or denied else "",
            transcript=_transcript(text, result.terminal_output),
            evidence={
                "stop_reason": result.stop_reason,
                "mcp": self.mcp.explain(config.role),
                # What the agent says it changed, so a reviewer can check the
                # claim against the worktree rather than taking it on trust.
                "files_changed": ", ".join(result.files_changed),
            },
        )

    def _reconcile_capabilities(self, client: AcpClient) -> None:
        """Drop capabilities the connected agent does not actually offer."""
        if not client.capabilities.supports("loadSession"):
            self.capabilities.discard(RunnerCapability.AGENT_SESSION)
        if not client.capabilities.prompt_capabilities.get("image", True):
            self.capabilities.discard(RunnerCapability.FILE_ACCESS)

    async def cancel(self, task_id: str) -> bool:
        client = self._clients.get(task_id)
        if client is None:
            return False
        await client.cancel()
        return True


def _transcript(text: str, terminal: str) -> str:
    """Keep terminal output in the transcript, labelled, not interleaved blindly."""
    if not terminal:
        return text
    return f"{text}\n\n--- terminal ---\n{terminal}" if text else terminal


async def allow_read_only(request: PermissionRequest) -> bool:
    """Permission policy that grants only non-mutating tool calls."""
    kind = str(request.raw.get("toolCall", {}).get("kind", "")).lower()
    return kind in ("read", "fetch", "search")
