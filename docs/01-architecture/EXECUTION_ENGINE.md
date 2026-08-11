# Execution Engine

Components: Run Coordinator, Scheduler, Worktree Manager, Attempt Manager, Integration Manager, Gate Coordinator.

A task runs only when dependencies succeed, Goal is active, concurrency/write scope is safe, budget permits and model/runner are available.

Failure classes: transient provider, deterministic test, quality, integration, policy, budget, cancellation. Each has explicit retry/escalation.

## Cancelling a run

`POST /api/runs/{id}/cancel` records the request; the runner checks it between
tasks and winds down. Cancellation is cooperative because killing the coroutine
mid-flight would interrupt a transaction between a state change and the event
that explains it — the one thing this runtime promises never happens. What is
not cooperative is the attempt already talking to a model: that is cancelled
outright, because waiting for it is exactly what the caller asked to stop.

A task that never started is recorded CANCELLED, not FAILED. It did not fail,
and recording it as a failure would make a run that was stopped on purpose look
like one that went wrong.

Two modelling defects surfaced while wiring this up, both now fixed: `PLANNED`
had no path to `CANCELLED`, so stopping a run before its tasks started meant
marking them `READY` first — a lie the state machine forced on the caller — and
`BLOCKED` was a dead end that nothing could ever leave. `Harness._active_tasks`
was declared and never filled, which made every `cancel_task` call quietly
return `False`.
