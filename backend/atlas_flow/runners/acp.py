"""ACP runner — preferred transport between Atlas Harness and coding agents."""

from __future__ import annotations

from atlas_flow.acp.client import AcpClient, PermissionPolicy, PermissionRequest
from atlas_flow.acp.protocol import AcpError
from atlas_flow.harness.runner import (
    Runner,
    RunnerCapability,
    RunnerConfig,
    RunnerResult,
)


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
        self._clients: dict[str, AcpClient] = {}

    async def run(self, task_id: str, prompt: str, config: RunnerConfig) -> RunnerResult:
        client = AcpClient(permission_policy=self.permission_policy)
        self._clients[task_id] = client

        try:
            await client.start(self.command, cwd=self.cwd)
            await client.initialize()
            self._reconcile_capabilities(client)
            await client.new_session(self.cwd or ".")

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

        return RunnerResult(
            task_id=task_id,
            success=result.completed and not result.permissions_denied,
            output=result.text,
            error=denied if not result.completed or denied else "",
            transcript=result.text,
            evidence={"stop_reason": result.stop_reason},
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


async def allow_read_only(request: PermissionRequest) -> bool:
    """Permission policy that grants only non-mutating tool calls."""
    kind = str(request.raw.get("toolCall", {}).get("kind", "")).lower()
    return kind in ("read", "fetch", "search")
