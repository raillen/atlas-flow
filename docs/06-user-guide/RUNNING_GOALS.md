# Running Goals

## Goal Lifecycle

Goals live in `.ai/goals/{phase}/{goal-id}.yaml`. They follow the Project Atlas state machine:

`DRAFT → PLANNED → READY → ACTIVE → DONE`

## How a Run Works

1. **Select a Goal** — only LOCKED goals can be executed.
2. **Plan** — the planner decomposes into a DAG of tasks with dependencies, write scopes, and gates.
3. **Execute** — the scheduler runs tasks in topological order. Mutable tasks run in isolated worktrees.
4. **Verify** — gate coordinator checks build, tests, review, and documentation evidence.
5. **Complete** — a run reaches DONE only when all required gates have passed evidence.

## Model Routing

Atlas Flow routes tasks to models based on role and risk:
- **DeepSeek V4 Pro** — architecture, reasoning, security review
- **MiMo V2.5 Pro** — implementation, refactors, integration
- **GPT-5.6 Luna** — exploration, tests, documentation (when Command Code exposes it)

The router uses deterministic ordered preference with bounded fallbacks.
Cross-provider diversity is preferred for high-risk review.

## Autonomy Modes

Configured in `.ai/orchestration/autonomy-policy.yaml`:
- **controlled** — planning and integration require human approval
- **agentic** — automatic within bounded retries, gate gated (default)
- **autonomous** — full auto, exceptions escalate

## Recovery

If a run crashes: reload durable state from SQLite, reconcile worktrees,
re-attach sessions where supported, never re-run succeeded tasks without
explicit reason.
