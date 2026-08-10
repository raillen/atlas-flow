# Validation Report

Generated: 2026-08-10

## Automated checks

| Check | Command | Result |
|-------|---------|--------|
| Python lint | `uv run --project backend ruff check .` | PASS |
| Python types | `uv run --project backend mypy` | PASS (strict, 50 files) |
| Python tests | `uv run --project backend pytest` | PASS — 183 tests |
| TypeScript build | `pnpm run typecheck` | PASS |
| JS lint | `pnpm run lint` | PASS |
| JS tests | `pnpm run test` | PASS — 18 tests |
| Docs links | `python scripts/validate_docs.py` | PASS |
| Goal contracts | `python scripts/validate_goals.py` | PASS — 11 Goals, 0 DONE |
| Command Code | `scripts/validate_command_code.sh` | PASS — 9 agents, 15 skills |

Run everything with `scripts/validate_all.sh`.

Roughly 7,000 lines of source are covered by roughly 5,600 lines of tests.

## Test coverage by subsystem

| Area | Tests | What is actually exercised |
|------|-------|----------------------------|
| Project Atlas loader | 10 | Real manifests, incompatible versions, cwd independence |
| Discuss and Decision Ledger | 24 | Lifecycle, persistence across restart, ADR generation |
| Execution runtime | 20 | Transactional transitions, durable state, crash recovery |
| Atlas Harness | 12 | Attempt persistence, capability negotiation, failure paths |
| ACP | 17 | Live agent subprocess, permissions, protocol errors |
| Planner and worktrees | 26 | Real git worktrees, conflict detection, parallel isolation |
| Goal execution | 5 | Plan to integrated commits, end to end |
| Verification and evidence | 24 | Gate rules, evidence persistence, DONE enforcement |
| Model routing | 12 | Role routing, fallback, scorecard |
| API | 27 | Every endpoint against the real project, path traversal, event stream |
| Faults and security | 12 | Fault injection, security guard |

## Defects this pass found and fixed

1. **CI never ran the Python tests.** Both CI jobs used `working-directory: backend`, where `testpaths` does not resolve; pytest collected nothing and exited 5, and `scripts/validate_docs.py` did not exist at that path.
2. **`AtlasFlowConfig.load()` always raised `KeyError`.** It read a key from a partially built dict. The only API test never started the lifespan, so it went unnoticed.
3. **All operational state was in-memory.** `Persistence` defaulted to `file::memory:` and the API used that default, so nothing survived a restart despite ADR-010 and two recovery documents.
4. **Attempts were never persisted.** The Harness built `Attempt` objects, mutated them, and dropped them; the `attempts` table was always empty.
5. **`validate_compatibility` ignored its argument** and validated `Path.cwd()` instead of the opened project.
6. **`all_passed` exempted the review and documentation gates** even when a Goal declared them required.
7. **`advance_run` emitted `previous` and `next` as the same value**, making the event log unable to explain a transition.
8. **Concurrent integration raced on `HEAD`.** Two parallel tasks merging into the same branch killed one with `cannot lock ref`; integration is now serialized.
9. **Leaked aiosqlite connections** in tests surfaced as `Event loop is closed` warnings from unrelated tests.

## Known gaps

These are tracked in the Goal files, not hidden:

- **No LLM is ever invoked.** The router selects model identifiers; no client exists. The CLI and ACP runners are the only paths that perform work (P08).
- **Budget limits are configured but not enforced** during a run (P08).
- **The Tauri shell is the unmodified template** — no IPC commands, no packaging pipeline (P06, P09).
- **MCP forwarding and terminal/file event streaming over ACP** are not implemented (P04).
- **No independent review has been performed**, so the review gate is outstanding on every Goal (P00–P08).
- **No dogfooding on other project categories** (P10).

## How to run

```sh
# Backend
uv run --project backend uvicorn atlas_flow.api.app:create_app --factory

# Frontend (separate terminal)
pnpm --filter @atlas-flow/desktop dev
```

Open http://localhost:1420. The Plan tab lists the Goals in Git; starting one
executes it and switches to Build, which follows the run live.
