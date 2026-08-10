# Product Requirements

## Core
- PR-001 Discuss-to-Project: conversation produces Decisions, Open Questions, Constraints, Project Draft and final Project Atlas artifacts.
- PR-002 Recovery: a new session/model recovers from Git without prior chat.
- PR-003 Goal execution: Goals become dependency-aware execution plans.
- PR-004 Multi-agent: independent tasks use isolated worktrees with bounded concurrency.
- PR-005 Model routing: role-based preference, fallback, provider diversity and runtime availability checks.
- PR-006 Harness interoperability: ACP preferred; CLI/API fallbacks.
- PR-007 Verification: acceptance criteria map to deterministic checks and structured review evidence.
- PR-008 Human gates: Controlled, Agentic and Autonomous modes.
- PR-009 Observability: tasks, agents, models, worktrees, events, cost/usage, retries and evidence visible.
- PR-010 Recovery: interrupted runs resume without replaying completed work.
- PR-011 Local-first: local project/DB/transcripts by default.
- PR-012 Extensibility: new runners/providers/gates/context sources without changing core semantics.

## Non-functional
- crash-resilient operational state;
- deterministic Goal transition enforcement;
- safe cancellation;
- cross-platform desktop support;
- accessible keyboard-first UI;
- no silent acceptance weakening;
- no unbounded retry loops;
- no raw secrets in project files.
