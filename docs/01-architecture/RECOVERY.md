# Recovery

Handle app/OS/runner crashes, API timeout, rate limit, disconnect and forced kill.

Procedure: validate Git/Goal revision → load durable run state → reconcile worktrees/processes → reattach session if supported → otherwise new attempt with prior evidence → never rerun succeeded task without explicit reason → reevaluate gates after integration.

Recovery should be idempotent where possible.
