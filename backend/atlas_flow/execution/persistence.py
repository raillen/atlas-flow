"""SQLite persistence layer for operational state (P03)."""

from __future__ import annotations

import asyncio
import json

import aiosqlite

from atlas_flow.execution.models import (
    DomainEvent,
    EventType,
    Run,
    Task,
    TaskState,
)

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    goal_id TEXT NOT NULL,
    goal_revision TEXT NOT NULL,
    state TEXT NOT NULL,
    autonomy TEXT NOT NULL DEFAULT 'agentic',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    role TEXT,
    risk TEXT NOT NULL DEFAULT 'medium',
    scope TEXT NOT NULL DEFAULT '[]',
    state TEXT NOT NULL,
    dependencies TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    runner TEXT,
    model_provider TEXT,
    model_id TEXT,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error_msg TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE NOT NULL,
    timestamp TEXT NOT NULL,
    project_id TEXT NOT NULL,
    run_id TEXT,
    type TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    payload TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts(task_id);
"""

SHARED_MEMORY = "file::memory:?cache=shared"


class PersistenceError(Exception):
    """Raised when an operational persistence operation fails."""


class Persistence:

    def __init__(self, db_path: str = SHARED_MEMORY) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        async with self._lock:
            self._conn = await aiosqlite.connect(self.db_path)
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")
            await self._conn.executescript(SCHEMA)
            await self._conn.execute(
                "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            await self._conn.commit()
            self._initialized = True

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def save_run(self, run: Run) -> None:
        await self._execute(
            """INSERT OR REPLACE INTO runs
               (id, project_id, goal_id, goal_revision, state, autonomy,
                created_at, started_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.id, run.project_id, run.goal_id, run.goal_revision,
                run.state, run.autonomy, run.created_at,
                run.started_at, run.completed_at,
            ),
        )

    async def load_run(self, run_id: str) -> Run | None:
        assert self._conn is not None
        self._conn.row_factory = aiosqlite.Row
        cursor = await self._conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return Run(**dict(row))

    async def save_event(self, event: DomainEvent) -> None:
        await self._execute(
            """INSERT OR IGNORE INTO events
               (id, timestamp, project_id, run_id, type, version, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id, event.timestamp, event.project_id, event.run_id,
                event.type, event.version, json.dumps(event.payload),
            ),
        )

    async def load_events(self, run_id: str) -> list[DomainEvent]:
        assert self._conn is not None
        self._conn.row_factory = aiosqlite.Row
        cursor = await self._conn.execute(
            "SELECT * FROM events WHERE run_id = ? ORDER BY seq",
            (run_id,),
        )
        rows = await cursor.fetchall()
        return [
            DomainEvent(
                id=row["id"],
                timestamp=row["timestamp"],
                project_id=row["project_id"],
                run_id=row["run_id"],
                type=EventType(row["type"]),
                version=row["version"],
                payload=json.loads(row["payload"]),
            )
            for row in rows
        ]

    async def save_task(self, task: Task) -> None:
        await self._execute(
            """INSERT OR REPLACE INTO tasks
               (id, run_id, objective, role, risk, scope, state,
                dependencies, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.id, task.run_id, task.objective, task.role, task.risk,
                json.dumps(task.scope), task.state,
                json.dumps(task.dependencies), task.created_at,
            ),
        )

    async def load_tasks(self, run_id: str) -> list[Task]:
        assert self._conn is not None
        self._conn.row_factory = aiosqlite.Row
        cursor = await self._conn.execute(
            "SELECT * FROM tasks WHERE run_id = ?",
            (run_id,),
        )
        rows = await cursor.fetchall()
        return [
            Task(
                id=row["id"],
                run_id=row["run_id"],
                objective=row["objective"],
                role=row["role"],
                risk=row["risk"],
                scope=json.loads(row["scope"]),
                state=TaskState(row["state"]),
                dependencies=json.loads(row["dependencies"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def _execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        if not self._initialized or self._conn is None:
            raise PersistenceError("Persistence not initialized")
        async with self._lock:
            await self._conn.execute(sql, params)
            await self._conn.commit()
