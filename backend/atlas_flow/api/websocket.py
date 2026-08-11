"""AG-UI WebSocket transport for real-time agent events (P06).

Clients subscribe to a session and receive the run events the backend commits,
so the desktop follows execution as it happens instead of asking repeatedly.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from atlas_flow.acp.events import NormalizedUpdate
from atlas_flow.execution.models import DomainEvent

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
            await ws.send_json(_envelope(event_type, payload))
        except Exception:  # noqa: BLE001 - a dead socket is just a disconnect
            self.disconnect(session_id)

    async def broadcast(self, event_type: str, payload: dict[str, object]) -> None:
        """Send to every open session, dropping the ones that have gone away."""
        message = _envelope(event_type, payload)
        for session_id, ws in list(self._connections.items()):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                self.disconnect(session_id)

    def is_connected(self, session_id: str) -> bool:
        return session_id in self._connections

    @property
    def session_count(self) -> int:
        return len(self._connections)


def _envelope(event_type: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }


manager = ConnectionManager()


async def broadcast_domain_event(event: DomainEvent) -> None:
    """Persistence subscriber: push every committed run event to the clients."""
    await manager.broadcast(
        str(event.type),
        {
            "event_id": event.id,
            "run_id": event.run_id,
            "project_id": event.project_id,
            **event.payload,
        },
    )


async def broadcast_agent_event(task_id: str, event: NormalizedUpdate) -> None:
    """Runner subscriber: push agent narration to the clients as it arrives.

    These are not persisted. A run's durable history is its domain events;
    terminal chunks and thoughts are volume, and storing every one of them
    would bury the audit trail rather than enrich it.
    """
    await manager.broadcast(event.event_name, {"task_id": task_id, **event.payload()})


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
    except json.JSONDecodeError:
        await manager.send_event(
            session_id, "atlas.error", {"reason": "malformed message"}
        )
        manager.disconnect(session_id)
