"""Performance instrumentation — timing decorators and budget assertions (P09)."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any


class Timer:
    _observations: defaultdict[str, list[float]] = defaultdict(list)

    @classmethod
    def record(cls, label: str, elapsed_ms: float) -> None:
        cls._observations[label].append(elapsed_ms)

    @classmethod
    def stats(cls, label: str) -> dict[str, float]:
        vals = cls._observations.get(label, [0.0])
        return {
            "count": len(vals),
            "p50_ms": percentile(vals, 50),
            "p95_ms": percentile(vals, 95),
            "p99_ms": percentile(vals, 99),
            "max_ms": max(vals) if vals else 0.0,
        }

    @classmethod
    def reset(cls) -> None:
        cls._observations.clear()


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (p / 100.0) * (len(sorted_data) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_data) - 1)
    frac = idx - lo
    return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac


def timed(
    label: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that records execution time of a callable."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - t0) * 1000
                Timer.record(label or func.__name__, elapsed)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - t0) * 1000
                Timer.record(label or func.__name__, elapsed)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return wrapper
        return sync_wrapper

    return decorator


class Budget:
    """Budget assertions for performance gates."""

    @staticmethod
    def assert_p95(label: str, max_ms: float) -> None:
        stats = Timer.stats(label)
        p95 = stats["p95_ms"]
        if p95 > max_ms:
            raise PerformanceBudgetError(
                f"P95 for '{label}': {p95:.1f}ms exceeds budget of {max_ms}ms"
            )


class PerformanceBudgetError(Exception):
    """Raised when a performance budget is exceeded."""
