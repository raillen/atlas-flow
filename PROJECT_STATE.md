# Current Project State

**Project:** Atlas Flow
**Framework:** Project Atlas Framework 0.1.0
**Status:** In development — 0 of 11 Goals DONE
**Current phase:** P08 — Routing, Budgets and Scorecards (blocked on model invocation)

## How to read the Goal states

Every Goal was audited on 2026-08-10 against its own acceptance criteria. Goals
that had been marked DONE without meeting them were reopened; each Goal's
`history` records what was unmet, what has since been closed, and what still
blocks it.

No Goal is DONE, and that is now enforced rather than asserted:
`scripts/validate_goals.py` fails CI if a Goal declares state DONE without
passing evidence for every gate it declares required.

| Phase | Goal | State | Blocking |
|-------|------|-------|----------|
| P00 | Repository Foundation | ACTIVE | review gate |
| P01 | Project Atlas Integration | ACTIVE | review gate |
| P02 | Discuss and Decision Ledger | ACTIVE | review gate |
| P03 | Orchestration Runtime | ACTIVE | review gate |
| P04 | Atlas Harness | ACTIVE | MCP forwarding, terminal/file events, review gate |
| P05 | Goal Planner and DAG Execution | ACTIVE | review gate |
| P06 | Desktop Modes | ACTIVE | Tauri IPC and packaging, review gate |
| P07 | Verification and Evidence | ACTIVE | review gate |
| P08 | Routing, Budgets and Scorecards | ACTIVE | no LLM client, no budget enforcement |
| P09 | Hardening | PLANNED | depends on P08 |
| P10 | Beta and 1.0 Validation | PLANNED | depends on P09 |

The review gate is outstanding across the board because no independent review
has been performed. It is deliberately not being self-certified.

## What works end to end

Starting a Goal from the desktop decomposes it into one task per acceptance
criterion, schedules the tasks in dependency order, runs each one in its own git
worktree through a registered runner, integrates the result, records gate
evidence and streams every state change to the UI. Run state is durable and
survives a crash.

## Approved direction

- Atlas Flow is generic; no Brasa Engine-specific behavior.
- Project Atlas Framework is the source of protocol, registries, Goals and project knowledge.
- Atlas Flow is the reference execution/orchestration runtime.
- Chat/Discuss is a first-class mode that can turn conversation into Project Atlas documentation.
- Canonical project truth stays in Git.
- Operational execution state uses SQLite plus append-only events, under `.atlas-flow/`.
- Frontend: Tauri 2 + React + TypeScript.
- Frontend/runtime agent events: AG-UI.
- Coding-agent client protocol: ACP preferred; a generic CLI runner is the fallback.
- Tool integration: MCP.
- Backend/orchestration core: Python, reusing Project Atlas.
- Atlas Harness is a meta-harness coordinating existing coding agents.
- Command Code is the development harness.
- Primary models: DeepSeek V4 Pro and MiMo V2.5 Pro.
- GPT-5.6 Luna is used for efficient/high-volume roles when available in Command Code.

## Next action

Close P08 by implementing model invocation: the router selects a model for every
task and feeds the scorecard, but nothing calls one. Until an agent actually runs,
the CLI and ACP runners are the only paths that perform work.
