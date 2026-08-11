"""Durable ACP session ids, so a restart can resume rather than start over (P04).

An agent session holds everything the agent has read and concluded. Losing it
because Atlas Flow restarted means the next attempt re-reads the repository and
re-derives what it already knew — the work is repeated, and the user pays for
it twice.

Only the identifier is stored. The conversation itself lives in the agent; this
is a pointer to it, and a pointer that turns out to be stale is a reason to
open a new session, never a reason to fail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from atlas_flow.execution.persistence import Persistence

ACP_SCHEMA = """
CREATE TABLE IF NOT EXISTS acp_sessions (
    task_id TEXT NOT NULL,
    runner TEXT NOT NULL,
    session_id TEXT NOT NULL,
    cwd TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    PRIMARY KEY (task_id, runner)
);
"""


@dataclass
class StoredSession:
    task_id: str
    runner: str
    session_id: str
    cwd: str
    created_at: str
    last_used_at: str


class AcpSessionStore:
    """Remembers which agent session belongs to which task."""

    def __init__(self, persistence: Persistence) -> None:
        self.db = persistence

    async def initialize(self) -> None:
        await self.db.run_script(ACP_SCHEMA)

    async def remember(
        self, task_id: str, runner: str, session_id: str, cwd: str = ""
    ) -> None:
        now = _now_iso()
        await self.db.execute(
            """INSERT INTO acp_sessions
                   (task_id, runner, session_id, cwd, created_at, last_used_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(task_id, runner) DO UPDATE SET
                   session_id = excluded.session_id,
                   cwd = excluded.cwd,
                   last_used_at = excluded.last_used_at""",
            (task_id, runner, session_id, cwd, now, now),
        )

    async def recall(self, task_id: str, runner: str) -> StoredSession | None:
        rows = await self.db.query(
            "SELECT * FROM acp_sessions WHERE task_id = ? AND runner = ?",
            (task_id, runner),
        )
        if not rows:
            return None
        row = rows[0]
        return StoredSession(
            task_id=str(row["task_id"]),
            runner=str(row["runner"]),
            session_id=str(row["session_id"]),
            cwd=str(row["cwd"]),
            created_at=str(row["created_at"]),
            last_used_at=str(row["last_used_at"]),
        )

    async def touch(self, task_id: str, runner: str) -> None:
        await self.db.execute(
            "UPDATE acp_sessions SET last_used_at = ? WHERE task_id = ? AND runner = ?",
            (_now_iso(), task_id, runner),
        )

    async def forget(self, task_id: str, runner: str) -> None:
        """Drop a session the agent no longer recognizes."""
        await self.db.execute(
            "DELETE FROM acp_sessions WHERE task_id = ? AND runner = ?",
            (task_id, runner),
        )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
