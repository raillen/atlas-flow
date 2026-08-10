"""AG-UI WebSocket transport for real-time agent events (P06)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[session_id] = ws

    def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)

    async def send_event(
        self, session_id: str, event_type: str, payload: dict[str, object]
    ) -> None:
        ws = self._connections.get(session_id)
        if ws is None:
            return
        try:
            await ws.send_json({
                "type": event_type,
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": payload,
            })
        except Exception:
            self.disconnect(session_id)

    def is_connected(self, session_id: str) -> bool:
        return session_id in self._connections


manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def ag_ui_socket(ws: WebSocket, session_id: str) -> None:
    await manager.connect(session_id, ws)
    try:
        while True:
            raw = await ws.receive_text()
            message = json.loads(raw)
            kind = message.get("kind", "message")
            if kind == "message":
                await manager.send_event(
                    session_id,
                    "atlas.discuss.message",
                    {"content": message.get("content", ""), "role": "user"},
                )
            elif kind == "decision_propose":
                await manager.send_event(
                    session_id,
                    "atlas.decision.proposed",
                    message.get("data", {}),
                )
    except WebSocketDisconnect:
        manager.disconnect(session_id)
