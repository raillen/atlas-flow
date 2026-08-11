"""SQLite persistence layer for operational state (P03)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.execution.models import (
    Attempt,
    AttemptState,
    DomainEvent,
    EventType,
    Run,
    RunState,
    Task,
    TaskState,
    can_transition,
)
from atlas_flow.execution.plans import PlanRecord, PlanState
from atlas_flow.workspace import ensure_private_dir

if TYPE_CHECKING:
    # Evidence lives with the verification engine, which imports this module;
    # the annotation-only import keeps the dependency one-directional at runtime.
    from atlas_flow.verification.gates import Evidence as EvidenceRow

EventListener = Callable[[DomainEvent], Awaitable[None]]

SCHEMA_VERSION = 3

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

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    run_id TEXT,
    task_id TEXT,
    gate TEXT NOT NULL,
    kind TEXT NOT NULL,
    uri TEXT NOT NULL DEFAULT '',
    digest TEXT NOT NULL DEFAULT '',
    verdict TEXT NOT NULL,
    attached_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_goal ON evidence(goal_id);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts(task_id);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    goal_id TEXT NOT NULL,
    goal_revision TEXT NOT NULL,
    state TEXT NOT NULL,
    autonomy TEXT NOT NULL,
    runner TEXT NOT NULL,
    integration_target TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tasks TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_plans_goal ON plans(goal_id);
"""

SHARED_MEMORY = "file::memory:?cache=shared"

_UPSERT_RUN = """
INSERT OR REPLACE INTO runs
    (id, project_id, goal_id, goal_revision, state, autonomy,
     created_at, started_at, completed_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPSERT_TASK = """
INSERT OR REPLACE INTO tasks
    (id, run_id, objective, role, risk, scope, state, dependencies, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPSERT_ATTEMPT = """
INSERT OR REPLACE INTO attempts
    (id, task_id, run_id, runner, model_provider, model_id, state,
     created_at, started_at, completed_at, error_msg)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_EVENT = """
INSERT OR IGNORE INTO events
    (id, timestamp, project_id, run_id, type, version, payload)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""


def _run_params(run: Run) -> tuple[object, ...]:
    return (
        run.id, run.project_id, run.goal_id, run.goal_revision,
        run.state, run.autonomy, run.created_at,
        run.started_at, run.completed_at,
    )


def _task_params(task: Task) -> tuple[object, ...]:
    return (
        task.id, task.run_id, task.objective, task.role, task.risk,
        json.dumps(task.scope), task.state,
        json.dumps(task.dependencies), task.created_at,
    )


def _attempt_params(attempt: Attempt) -> tuple[object, ...]:
    return (
        attempt.id, attempt.task_id, attempt.run_id, attempt.runner,
        attempt.model_provider, attempt.model_id, attempt.state,
        attempt.created_at, attempt.started_at, attempt.completed_at,
        attempt.error_msg,
    )


def _event_params(event: DomainEvent) -> tuple[object, ...]:
    return (
        event.id, event.timestamp, event.project_id, event.run_id,
        event.type, event.version, json.dumps(event.payload),
    )


class PersistenceError(Exception):
    """Raised when an operational persistence operation fails."""


class InvalidTransition(PersistenceError):
    """Raised when a state change is not allowed by the state machine."""


class Persistence:
    """Operational state store.

    Defaults to a file-backed database so run state survives a crash or a
    restart; pass SHARED_MEMORY explicitly for tests that do not need
    durability. Canonical Goal authority stays in Git — this database is
    strictly operational (ADR-009, ADR-010).
    """

    def __init__(self, db_path: str | Path = SHARED_MEMORY) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._initialized = False
        self._listeners: list[EventListener] = []

    @classmethod
    def from_config(cls, config: AtlasFlowConfig) -> Persistence:
        return cls(config.database_path)

    @property
    def is_durable(self) -> bool:
        return isinstance(self.db_path, Path) or ":memory:" not in str(self.db_path)

    async def initialize(self) -> None:
        async with self._lock:
            if isinstance(self.db_path, Path):
                ensure_private_dir(self.db_path.parent)
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
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
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None
            self._initialized = False

    def subscribe(self, listener: EventListener) -> None:
        """Observe events as they are committed.

        Listeners run after the commit, never inside the transaction: a slow or
        failing subscriber must not be able to roll back durable state or hold
        the write lock.
        """
        self._listeners.append(listener)

    async def _publish(self, event: DomainEvent) -> None:
        for listener in self._listeners:
            try:
                await listener(event)
            except Exception:  # noqa: BLE001 - a subscriber must not break a run
                continue

    def _require_conn(self) -> aiosqlite.Connection:
        if not self._initialized or self._conn is None:
            raise PersistenceError("Persistence not initialized")
        return self._conn

    async def save_plan(self, plan: PlanRecord) -> None:
        existing = await self.load_plan(plan.id)
        if existing is not None and existing.state != PlanState.DRAFT:
            if existing.state == PlanState.LOCKED and plan.state == PlanState.CONSUMED:
                pass
            elif existing.model_dump() != plan.model_dump():
                raise PersistenceError(f"Plan {plan.id} is immutable after {existing.state}")
            else:
                return
        await self._execute(
            """INSERT OR REPLACE INTO plans
               (id, project_id, goal_id, goal_revision, state, autonomy, runner,
                integration_target, created_at, tasks)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plan.id,
                plan.project_id,
                plan.goal_id,
                plan.goal_revision,
                str(plan.state),
                plan.autonomy,
                plan.runner,
                plan.integration_target,
                plan.created_at,
                plan.model_dump_json(include={"tasks"}),
            ),
        )

    async def load_plan(self, plan_id: str) -> PlanRecord | None:
        conn = self._require_conn()
        cursor = await conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return PlanRecord(
            id=row["id"],
            project_id=row["project_id"],
            goal_id=row["goal_id"],
            goal_revision=row["goal_revision"],
            state=PlanState(row["state"]),
            autonomy=row["autonomy"],
            runner=row["runner"],
            integration_target=row["integration_target"],
            created_at=row["created_at"],
            tasks=json.loads(row["tasks"]).get("tasks", []),
        )

    async def list_plans(self, goal_id: str | None = None) -> list[PlanRecord]:
        conn = self._require_conn()
        if goal_id is None:
            cursor = await conn.execute("SELECT * FROM plans ORDER BY created_at DESC")
        else:
            cursor = await conn.execute(
                "SELECT * FROM plans WHERE goal_id = ? ORDER BY created_at DESC",
                (goal_id,),
            )
        rows = await cursor.fetchall()
        plans: list[PlanRecord] = []
        for row in rows:
            plan = await self.load_plan(row["id"])
            if plan is not None:
                plans.append(plan)
        return plans

    async def save_run(self, run: Run) -> None:
        await self._execute(_UPSERT_RUN, _run_params(run))

    async def load_run(self, run_id: str) -> Run | None:
        conn = self._require_conn()
        cursor = await conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return Run(**dict(row))

    async def list_runs(self, project_id: str | None = None) -> list[Run]:
        conn = self._require_conn()
        if project_id is None:
            cursor = await conn.execute("SELECT * FROM runs ORDER BY created_at DESC")
        else:
            cursor = await conn.execute(
                "SELECT * FROM runs WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            )
        rows = await cursor.fetchall()
        return [Run(**dict(row)) for row in rows]

    async def save_event(self, event: DomainEvent) -> None:
        await self._execute(_INSERT_EVENT, _event_params(event))
        await self._publish(event)

    async def load_events(self, run_id: str) -> list[DomainEvent]:
        conn = self._require_conn()
        cursor = await conn.execute(
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
        await self._execute(_UPSERT_TASK, _task_params(task))

    async def load_tasks(self, run_id: str) -> list[Task]:
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM tasks WHERE run_id = ? ORDER BY created_at",
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

    async def save_attempt(self, attempt: Attempt) -> None:
        await self._execute(_UPSERT_ATTEMPT, _attempt_params(attempt))

    async def load_attempts(self, run_id: str) -> list[Attempt]:
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM attempts WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        )
        return [Attempt(**dict(row)) for row in await cursor.fetchall()]

    async def load_attempts_for_task(self, task_id: str) -> list[Attempt]:
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM attempts WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        )
        return [Attempt(**dict(row)) for row in await cursor.fetchall()]

    async def save_evidence(self, evidence: EvidenceRow) -> None:
        await self._execute(
            """INSERT OR REPLACE INTO evidence
                   (id, goal_id, run_id, task_id, gate, kind, uri, digest,
                    verdict, attached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                evidence.id, evidence.goal_id, evidence.run_id, evidence.task_id,
                str(evidence.gate), evidence.kind, evidence.uri, evidence.digest,
                str(evidence.verdict), evidence.attached_at,
            ),
        )

    async def load_evidence(self, goal_id: str) -> list[EvidenceRow]:
        from atlas_flow.verification.gates import Evidence, GateKind, GateVerdict

        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM evidence WHERE goal_id = ? ORDER BY attached_at",
            (goal_id,),
        )
        return [
            Evidence(
                id=row["id"],
                goal_id=row["goal_id"],
                gate=GateKind(row["gate"]),
                kind=row["kind"],
                uri=row["uri"],
                digest=row["digest"],
                attached_at=row["attached_at"],
                verdict=GateVerdict(row["verdict"]),
                run_id=row["run_id"],
                task_id=row["task_id"],
            )
            for row in await cursor.fetchall()
        ]

    async def record_run_transition(
        self, run: Run, to_state: RunState, event: DomainEvent
    ) -> Run:
        """Move a Run to a new state and append its event atomically.

        Either both the row and the event land, or neither does. A partially
        applied transition would leave the event log unable to explain the
        current state, which is what recovery reads back.
        """
        self._guard(run.state, to_state, "run", run.id)
        updated = run.model_copy(update={"state": to_state})
        await self._transaction(
            (_UPSERT_RUN, _run_params(updated)),
            (_INSERT_EVENT, _event_params(event)),
        )
        await self._publish(event)
        return updated

    async def record_task_transition(
        self, task: Task, to_state: TaskState, event: DomainEvent
    ) -> Task:
        self._guard(task.state, to_state, "task", task.id)
        updated = task.model_copy(update={"state": to_state})
        await self._transaction(
            (_UPSERT_TASK, _task_params(updated)),
            (_INSERT_EVENT, _event_params(event)),
        )
        await self._publish(event)
        return updated

    async def record_attempt_transition(
        self, attempt: Attempt, to_state: AttemptState, event: DomainEvent
    ) -> Attempt:
        self._guard(attempt.state, to_state, "attempt", attempt.id)
        updated = attempt.model_copy(update={"state": to_state})
        await self._transaction(
            (_UPSERT_ATTEMPT, _attempt_params(updated)),
            (_INSERT_EVENT, _event_params(event)),
        )
        await self._publish(event)
        return updated

    @staticmethod
    def _guard(from_state: str, to_state: str, domain: str, entity_id: str) -> None:
        if not can_transition(from_state, to_state, domain):
            raise InvalidTransition(
                f"{domain} {entity_id}: {from_state} -> {to_state} is not a valid transition"
            )

    async def _transaction(self, *statements: tuple[str, tuple[object, ...]]) -> None:
        conn = self._require_conn()
        async with self._lock:
            try:
                for sql, params in statements:
                    await conn.execute(sql, params)
            except Exception:
                await conn.rollback()
                raise
            await conn.commit()

    async def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        """Run a write statement.

        Satellite stores — the Decision Ledger, for one — keep their own tables
        in this same database so a discussion and the run it produced share one
        transaction log and one file to back up.
        """
        await self._execute(sql, params)

    async def query(
        self, sql: str, params: tuple[object, ...] = ()
    ) -> list[aiosqlite.Row]:
        conn = self._require_conn()
        cursor = await conn.execute(sql, params)
        return list(await cursor.fetchall())

    async def run_script(self, script: str) -> None:
        """Apply a satellite store's schema."""
        conn = self._require_conn()
        async with self._lock:
            await conn.executescript(script)
            await conn.commit()

    async def _execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        conn = self._require_conn()
        async with self._lock:
            await conn.execute(sql, params)
            await conn.commit()
