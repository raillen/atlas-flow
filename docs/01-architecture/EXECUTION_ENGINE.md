# Execution Engine

Components: Run Coordinator, Scheduler, Worktree Manager, Attempt Manager, Integration Manager, Gate Coordinator.

A task runs only when dependencies succeed, Goal is active, concurrency/write scope is safe, budget permits and model/runner are available.

Failure classes: transient provider, deterministic test, quality, integration, policy, budget, cancellation. Each has explicit retry/escalation.
