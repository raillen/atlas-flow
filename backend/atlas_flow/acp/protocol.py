"""JSON-RPC 2.0 over newline-delimited stdio — the ACP wire format.

The connection is bidirectional: Atlas Flow calls the agent, and the agent
calls back for things only the client can decide, such as permission to run a
tool. Both directions are multiplexed over the same pair of pipes, so the
reader loop has to route by message shape rather than assume request/response
alternation.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

JsonRpcParams = dict[str, Any]
RequestHandler = Callable[[JsonRpcParams], Awaitable[Any]]
NotificationHandler = Callable[[str, JsonRpcParams], Awaitable[None]]


class AcpError(Exception):
    """Transport or protocol failure while talking to an ACP agent."""


class AcpRemoteError(AcpError):
    """The agent answered with a JSON-RPC error object."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        self.code = code
        self.data = data
        super().__init__(f"ACP error {code}: {message}")


@dataclass
class _Pending:
    future: asyncio.Future[Any]
    method: str


@dataclass
class AcpConnection:
    """Owns the agent subprocess and the JSON-RPC framing over its stdio."""

    request_handlers: dict[str, RequestHandler] = field(default_factory=dict)
    on_notification: NotificationHandler | None = None

    _process: asyncio.subprocess.Process | None = field(default=None, init=False)
    _pending: dict[int, _Pending] = field(default_factory=dict, init=False)
    _next_id: int = field(default=0, init=False)
    _reader: asyncio.Task[None] | None = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)

    async def start(self, command: list[str], cwd: str | None = None) -> None:
        if not command:
            raise AcpError("ACP agent command is empty")
        try:
            self._process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        except FileNotFoundError as exc:
            raise AcpError(f"ACP agent not found: {command[0]}") from exc

        self._reader = asyncio.create_task(self._read_loop())

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def call(self, method: str, params: JsonRpcParams, timeout: float = 60.0) -> Any:
        """Send a request and wait for its response."""
        if not self.running:
            raise AcpError(f"Cannot call {method}: agent is not running")

        self._next_id += 1
        request_id = self._next_id
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = _Pending(future=future, method=method)

        await self._write(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            self._pending.pop(request_id, None)
            raise AcpError(f"ACP call '{method}' timed out after {timeout}s") from exc

    async def notify(self, method: str, params: JsonRpcParams) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def _write(self, message: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise AcpError("ACP connection is not open")
        process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        await process.stdin.drain()

    async def _read_loop(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    # Agents sometimes write diagnostics to stdout. Skipping a
                    # non-JSON line is better than tearing down a live session.
                    continue
                await self._dispatch(message)
        finally:
            self._fail_pending(AcpError("ACP agent closed the connection"))

    async def _dispatch(self, message: dict[str, Any]) -> None:
        if "method" in message and "id" in message:
            await self._handle_request(message)
        elif "method" in message:
            if self.on_notification is not None:
                await self.on_notification(message["method"], message.get("params") or {})
        elif "id" in message:
            self._handle_response(message)

    async def _handle_request(self, message: dict[str, Any]) -> None:
        method = message["method"]
        handler = self.request_handlers.get(method)
        if handler is None:
            await self._write({
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })
            return
        try:
            result = await handler(message.get("params") or {})
        except Exception as exc:  # noqa: BLE001 - reported to the agent as an error
            await self._write({
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {"code": -32603, "message": str(exc)},
            })
            return
        await self._write({"jsonrpc": "2.0", "id": message["id"], "result": result})

    def _handle_response(self, message: dict[str, Any]) -> None:
        pending = self._pending.pop(message["id"], None)
        if pending is None or pending.future.done():
            return
        if "error" in message:
            error = message["error"]
            pending.future.set_exception(
                AcpRemoteError(
                    error.get("code", -1), error.get("message", ""), error.get("data")
                )
            )
        else:
            pending.future.set_result(message.get("result"))

    def _fail_pending(self, error: Exception) -> None:
        for pending in self._pending.values():
            if not pending.future.done():
                pending.future.set_exception(error)
        self._pending.clear()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        process = self._process
        if process is not None and process.returncode is None:
            if process.stdin is not None:
                process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except TimeoutError:
                process.kill()
                await process.wait()

        if self._reader is not None:
            self._reader.cancel()
            # The reader is being torn down; whatever it was in the middle of
            # is no longer interesting.
            with suppress(asyncio.CancelledError, Exception):
                await self._reader

        self._fail_pending(AcpError("ACP connection closed"))
