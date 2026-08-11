# Performance Budgets

## Measured

`tests/integration/test_performance.py` measures the two budgets that are the
runtime's own responsibility and asserts them, so a regression fails the suite
rather than being noticed later:

| What | Budget | Measured on a developer machine |
| --- | --- | --- |
| Append one event to the durable store (p95, 200 samples) | <20 ms | ~0.5 ms |
| Read a 1000-event run log (p95, 20 samples) | <150 ms | ~32 ms |
| `GET /api/runs/{id}` (p95) | <150 ms | ~6 ms |
| `GET /api/goals` (p95) | <150 ms | ~47 ms |
| `GET /api/routing` (p95) | <150 ms | ~3 ms |

Each check reports p95, median and max so a number drifting toward its budget is
visible before it crosses it. `GET /api/goals` is the slowest by an order of
magnitude because it re-reads every Goal from Git on each request — well inside
budget, and the first place to look if it stops being.

A budget nobody measures is a wish; a budget measured so tightly that ordinary
scheduling noise trips it is worse, so every check is a p95 over enough samples
that one slow moment cannot decide the outcome.

## Not yet measured

Cold start, time-to-usable after opening a project, UI frame rate, and
transcript virtualization. These need a running desktop build and a fixture
project, neither of which is automated yet.

## Targets

Initial targets:
- cold start <3s on mid-range SSD desktop;
- medium fixture usable <2s after project open, background indexing allowed;
- UI 60 FPS target;
- local event append p95 <20ms;
- backend state to UI p95 <150ms local;
- large transcripts virtualized;
- context building exposes size/timing and avoids unnecessary full scans.
