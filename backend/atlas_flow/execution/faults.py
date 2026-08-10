"""Fault injection infrastructure (P09 reliability)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import StrEnum


class FaultKind(StrEnum):
    PROCESS_KILL = "process_kill"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    MALFORMED_OUTPUT = "malformed_output"
    GIT_CONFLICT = "git_conflict"
    SQLITE_CONTENTION = "sqlite_contention"
    CANCELLATION_DURING_WRITE = "cancellation_during_write"
    STALE_GOAL_REVISION = "stale_goal_revision"
    DISCONNECT = "disconnect"


@dataclass
class FaultPoint:
    kind: FaultKind
    target: str  # task_id, runner name, or "sqlite"
    trigger_count: int = 0  # 0 = always
    enabled: bool = True
    count: int = field(default=0, init=False)

    def should_trigger(self) -> bool:
        if not self.enabled:
            return False
        if self.trigger_count == 0:
            return True
        self.count += 1
        return self.count == self.trigger_count


class FaultInjector:
    """Central fault injection registry."""

    def __init__(self) -> None:
        self._points: dict[str, list[FaultPoint]] = {}
        self._faults_triggered: list[dict[str, object]] = []

    def register(self, scope: str, point: FaultPoint) -> None:
        self._points.setdefault(scope, []).append(point)

    def inject(self, scope: str, kind: FaultKind) -> bool:
        """Returns True if a fault should be triggered for this scope+kind."""
        points = self._points.get(scope, [])
        for fp in points:
            if fp.kind == kind and fp.should_trigger():
                self._faults_triggered.append(
                    {"scope": scope, "kind": kind, "target": fp.target}
                )
                return True
        return False

    def triggered_count(self, kind: FaultKind | None = None) -> int:
        if kind is None:
            return len(self._faults_triggered)
        return sum(1 for f in self._faults_triggered if f["kind"] == kind)

    def reset(self) -> None:
        self._points.clear()
        self._faults_triggered.clear()

    @asynccontextmanager
    async def timeout_guard(self, task_id: str, seconds: float = 5.0) -> AsyncIterator[None]:
        injector = self
        async def run() -> None:
            if injector.inject(task_id, FaultKind.TIMEOUT):
                await asyncio.sleep(0.1)
                raise TimeoutError(f"Injected timeout for {task_id}")
        try:
            yield
        except TimeoutError:
            self._faults_triggered.append(
                {"scope": task_id, "kind": FaultKind.TIMEOUT, "target": task_id}
            )
            raise
