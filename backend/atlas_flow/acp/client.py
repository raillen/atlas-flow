"""ACP client: session lifecycle, capability negotiation, permissions (P04).

Atlas Flow is the client. It negotiates capabilities on initialize and then
only uses what the agent actually advertised — an agent that does not support
a feature degrades to doing without it, never to a crash.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from atlas_flow.acp.protocol import AcpConnection, AcpError, JsonRpcParams

PROTOCOL_VERSION = 1


class PermissionOutcome(StrEnum):
    ALLOWED = "selected"
    DENIED = "cancelled"


@dataclass
class PermissionRequest:
    """An agent asking to do something the client must authorize."""

    session_id: str
    tool_name: str
    options: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def option_id(self, kind: str) -> str | None:
        """First option matching a kind such as 'allow_once' or 'reject_once'."""
        for option in self.options:
            if option.get("kind") == kind:
                identifier = option.get("optionId")
                return str(identifier) if identifier is not None else None
        return None


PermissionPolicy = Callable[[PermissionRequest], Awaitable[bool]]
UpdateListener = Callable[[str, dict[str, Any]], Awaitable[None]]


async def deny_all(request: PermissionRequest) -> bool:
    """Default policy: refuse anything nobody explicitly allowed.

    Silently granting an agent whatever it asks for would make the permission
    round-trip decorative. Callers opt into a looser policy deliberately.
    """
    return False


@dataclass
class AgentCapabilities:
    """What the agent said it can do, as returned from initialize."""

    protocol_version: int = PROTOCOL_VERSION
    raw: dict[str, Any] = field(default_factory=dict)

    def supports(self, name: str) -> bool:
        value = self.raw.get(name)
        if isinstance(value, bool):
            return value
        return bool(value)

    @property
    def prompt_capabilities(self) -> dict[str, Any]:
        value = self.raw.get("promptCapabilities")
        return value if isinstance(value, dict) else {}


@dataclass
class PromptResult:
    stop_reason: str = ""
    text: str = ""
    updates: list[dict[str, Any]] = field(default_factory=list)
    permissions_requested: list[PermissionRequest] = field(default_factory=list)
    permissions_denied: list[str] = field(default_factory=list)

    @property
    def completed(self) -> bool:
        return self.stop_reason in ("end_turn", "completed")


class AcpClient:
    """Drives one ACP agent process."""

    def __init__(
        self,
        permission_policy: PermissionPolicy | None = None,
        on_update: UpdateListener | None = None,
    ) -> None:
        self.connection = AcpConnection()
        self.connection.request_handlers["session/request_permission"] = (
            self._on_permission_request
        )
        self.connection.on_notification = self._on_notification

        self.permission_policy = permission_policy or deny_all
        self.on_update = on_update
        self.capabilities = AgentCapabilities()
        self.session_id: str | None = None

        self._updates: list[dict[str, Any]] = []
        self._permissions: list[PermissionRequest] = []
        self._denied: list[str] = []

    async def start(self, command: list[str], cwd: str | None = None) -> None:
        await self.connection.start(command, cwd=cwd)

    async def initialize(
        self, client_capabilities: dict[str, Any] | None = None
    ) -> AgentCapabilities:
        result = await self.connection.call(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "clientCapabilities": client_capabilities
                or {"fs": {"readTextFile": True, "writeTextFile": True}},
            },
        )
        if not isinstance(result, dict):
            raise AcpError("initialize returned no capabilities")

        negotiated = int(result.get("protocolVersion", PROTOCOL_VERSION))
        if negotiated > PROTOCOL_VERSION:
            raise AcpError(
                f"Agent speaks ACP v{negotiated}; this client supports "
                f"v{PROTOCOL_VERSION}"
            )

        raw = result.get("agentCapabilities")
        self.capabilities = AgentCapabilities(
            protocol_version=negotiated,
            raw=raw if isinstance(raw, dict) else {},
        )
        return self.capabilities

    async def new_session(
        self, cwd: str, mcp_servers: list[dict[str, Any]] | None = None
    ) -> str:
        result = await self.connection.call(
            "session/new", {"cwd": cwd, "mcpServers": mcp_servers or []}
        )
        if not isinstance(result, dict) or "sessionId" not in result:
            raise AcpError("session/new did not return a sessionId")
        self.session_id = str(result["sessionId"])
        return self.session_id

    async def load_session(self, session_id: str, cwd: str) -> bool:
        """Resume a previous session when the agent supports it."""
        if not self.capabilities.supports("loadSession"):
            return False
        await self.connection.call(
            "session/load", {"sessionId": session_id, "cwd": cwd}
        )
        self.session_id = session_id
        return True

    async def prompt(self, text: str, timeout: float = 300.0) -> PromptResult:
        if self.session_id is None:
            raise AcpError("prompt called before a session was created")

        self._updates = []
        self._permissions = []
        self._denied = []

        result = await self.connection.call(
            "session/prompt",
            {
                "sessionId": self.session_id,
                "prompt": [{"type": "text", "text": text}],
            },
            timeout=timeout,
        )

        stop_reason = ""
        if isinstance(result, dict):
            stop_reason = str(result.get("stopReason", ""))

        return PromptResult(
            stop_reason=stop_reason,
            text=self._collected_text(),
            updates=list(self._updates),
            permissions_requested=list(self._permissions),
            permissions_denied=list(self._denied),
        )

    async def cancel(self) -> None:
        if self.session_id is None:
            return
        await self.connection.notify("session/cancel", {"sessionId": self.session_id})

    async def close(self) -> None:
        await self.connection.close()

    def _collected_text(self) -> str:
        chunks: list[str] = []
        for update in self._updates:
            content = update.get("content")
            if isinstance(content, dict) and content.get("type") == "text":
                chunks.append(str(content.get("text", "")))
        return "".join(chunks)

    async def _on_notification(self, method: str, params: JsonRpcParams) -> None:
        if method != "session/update":
            return
        update = params.get("update")
        if isinstance(update, dict):
            self._updates.append(update)
            if self.on_update is not None:
                await self.on_update(str(update.get("sessionUpdate", "")), update)

    async def _on_permission_request(self, params: JsonRpcParams) -> dict[str, Any]:
        tool_call = params.get("toolCall")
        request = PermissionRequest(
            session_id=str(params.get("sessionId", "")),
            tool_name=str(
                (tool_call or {}).get("title") or (tool_call or {}).get("kind") or "unknown"
            ),
            options=list(params.get("options") or []),
            raw=dict(params),
        )
        self._permissions.append(request)

        allowed = await self.permission_policy(request)
        if allowed:
            option = request.option_id("allow_once") or request.option_id("allow_always")
            if option is not None:
                return {"outcome": {"outcome": "selected", "optionId": option}}

        self._denied.append(request.tool_name)
        option = request.option_id("reject_once")
        if option is not None:
            return {"outcome": {"outcome": "selected", "optionId": option}}
        return {"outcome": {"outcome": "cancelled"}}
