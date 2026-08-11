"""Asking a run to stop, and letting it stop tidily.

Cancellation is cooperative on purpose. Killing the coroutine mid-flight would
interrupt a transaction between the state change and the event that explains
it, which is the one thing the execution runtime promises never to happen.
Recovery exists for the case where the process dies anyway; this is for the
case where somebody simply wants the run to stop.

A request lives in memory, not in the database. It is only meaningful while a
run is executing, and a run does not survive the process that was executing it
— after a restart there is nothing left to ask, and `recover_run` reconciles
what the crash left behind.
"""

from __future__ import annotations


class CancellationRegistry:
    """Which runs have been asked to stop, and why."""

    def __init__(self) -> None:
        self._requested: dict[str, str] = {}

    def request(self, run_id: str, reason: str = "cancelled by request") -> None:
        self._requested.setdefault(run_id, reason)

    def is_requested(self, run_id: str) -> bool:
        return run_id in self._requested

    def reason(self, run_id: str) -> str:
        return self._requested.get(run_id, "")

    def clear(self, run_id: str) -> None:
        """Forget a run that has finished winding down."""
        self._requested.pop(run_id, None)

    @property
    def pending(self) -> list[str]:
        return sorted(self._requested)
