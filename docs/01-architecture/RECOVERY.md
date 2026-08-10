# Recovery

Handle app/OS/runner crashes, API timeout, rate limit, disconnect and forced kill.

## Procedure

Validate Git/Goal revision → load durable run state → reconcile orphaned work →
reattach the agent session if the runner supports it → otherwise start a new
attempt carrying the prior evidence → never rerun a succeeded task without an
explicit reason → reevaluate gates after integration.

## Reconciling orphaned work

A task or attempt left in a running state has no live process behind it once the
runtime restarts. `recover_run` closes both as failed and records why, then moves
the run to BLOCKED if any task was interrupted.

Failed tasks are retryable, which is what makes recovery idempotent: running it a
second time finds nothing left to reconcile. Leaving orphans in RUNNING would be
worse than closing them — the UI would show work that nothing is doing, and the
scheduler would never release the tasks waiting on it.

## Worktrees

Worktrees belonging to failed or cancelled tasks are left on disk for inspection.
Removal refuses to discard uncommitted work unless forced, so recovery never
destroys output a run had already produced.
