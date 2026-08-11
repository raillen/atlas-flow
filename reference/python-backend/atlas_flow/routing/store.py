"""Durable routing memory: scorecard observations and route decisions (P08).

A scorecard that resets every restart cannot influence anything — the point of
observing outcomes is that tomorrow's routing knows what happened today. Route
decisions are stored for the opposite reason: after a run, someone needs to be
able to ask why a model was chosen and get an answer that is not a guess.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from atlas_flow.execution.persistence import Persistence
from atlas_flow.routing.router import ModelScorecard, RouteDecision

ROUTING_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_observations (
    id TEXT PRIMARY KEY,
    model_key TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    success INTEGER NOT NULL,
    latency_ms REAL NOT NULL DEFAULT 0,
    run_id TEXT,
    task_id TEXT,
    observed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS route_decisions (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    task_id TEXT NOT NULL,
    role TEXT NOT NULL,
    selected TEXT,
    candidates TEXT NOT NULL DEFAULT '[]',
    reason TEXT NOT NULL DEFAULT '',
    fallback_attempts INTEGER NOT NULL DEFAULT 0,
    decided_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_observations_model ON model_observations(model_key);
CREATE INDEX IF NOT EXISTS idx_route_decisions_run ON route_decisions(run_id);
"""


@dataclass
class ModelStats:
    model_key: str
    uses: int = 0
    successes: int = 0
    failures: int = 0
    average_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.uses if self.uses else 0.0


@dataclass
class RoutingSnapshot:
    """What the router knows, for the API and the Review screen."""

    available: list[str] = field(default_factory=list)
    reachable: bool = False
    reason: str = ""
    stats: list[ModelStats] = field(default_factory=list)


class RoutingStore:
    """Reads and writes routing memory."""

    def __init__(self, persistence: Persistence) -> None:
        self.db = persistence

    async def initialize(self) -> None:
        await self.db.run_script(ROUTING_SCHEMA)

    async def record_observation(
        self,
        model_key: str,
        success: bool,
        role: str = "",
        latency_ms: float = 0.0,
        run_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        await self.db.execute(
            """INSERT INTO model_observations
                   (id, model_key, role, success, latency_ms, run_id, task_id, observed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"obs-{uuid.uuid4().hex[:12]}", model_key, role, int(success),
                latency_ms, run_id, task_id, _now_iso(),
            ),
        )

    async def record_decision(
        self,
        decision: RouteDecision,
        task_id: str,
        run_id: str | None = None,
    ) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO route_decisions
                   (id, run_id, task_id, role, selected, candidates, reason,
                    fallback_attempts, decided_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"route-{uuid.uuid4().hex[:12]}", run_id, task_id, decision.role,
                decision.selected.key if decision.selected else None,
                json.dumps([c.key for c in decision.candidates]),
                decision.reason, decision.fallback_attempts, _now_iso(),
            ),
        )

    async def stats(self) -> list[ModelStats]:
        rows = await self.db.query(
            """SELECT model_key,
                      COUNT(*) AS uses,
                      SUM(success) AS successes,
                      AVG(latency_ms) AS average_latency
               FROM model_observations
               GROUP BY model_key
               ORDER BY uses DESC"""
        )
        return [
            ModelStats(
                model_key=row["model_key"],
                uses=int(row["uses"]),
                successes=int(row["successes"] or 0),
                failures=int(row["uses"]) - int(row["successes"] or 0),
                average_latency_ms=float(row["average_latency"] or 0.0),
            )
            for row in rows
        ]

    async def decisions_for_run(self, run_id: str) -> list[dict[str, object]]:
        rows = await self.db.query(
            "SELECT * FROM route_decisions WHERE run_id = ? ORDER BY decided_at",
            (run_id,),
        )
        return [
            {
                "task_id": row["task_id"],
                "role": row["role"],
                "selected": row["selected"],
                "candidates": json.loads(row["candidates"]),
                "reason": row["reason"],
                "fallback_attempts": row["fallback_attempts"],
            }
            for row in rows
        ]

    async def restore(self, scorecard: ModelScorecard) -> ModelScorecard:
        """Seed an in-memory scorecard from what previous runs observed."""
        for stat in await self.stats():
            for _ in range(stat.successes):
                scorecard.observe(stat.model_key, success=True)
            for _ in range(stat.failures):
                scorecard.observe(stat.model_key, success=False)
        return scorecard


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
