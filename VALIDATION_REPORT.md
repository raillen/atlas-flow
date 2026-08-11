# Validation Report

Generated: 2026-08-10

## Automated checks

| Check | Command | Result |
|-------|---------|--------|
| Python lint | `uv run --project backend ruff check .` | PASS |
| Python types | `uv run --project backend mypy` | PASS (strict, 56 files) |
| Python tests | `uv run --project backend pytest` | PASS — 311 tests |
| TypeScript build | `pnpm run typecheck` | PASS |
| JS lint | `pnpm run lint` | PASS |
| JS tests | `pnpm run test` | PASS — 56 tests, including an axe-core DOM audit |
| Docs links | `python scripts/validate_docs.py` | PASS |
| Goal contracts | `python scripts/validate_goals.py` | PASS — 11 Goals, 0 DONE |
| Command Code | `scripts/validate_command_code.sh` | PASS — 9 agents, 15 skills |
| Desktop shell | `cargo fmt`, `clippy -D warnings`, `cargo test` | PASS — 9 tests |
| Dependency audit | `pip-audit`, `pnpm audit` | PASS — one advisory found and fixed |
| Every gate at once | `sh scripts/bootstrap.sh && sh scripts/run_gates.sh` | PASS |
| Packaging | `sh scripts/package_smoke.sh` | PASS — deb bundle, CycloneDX SBOM (791 components), SHA256SUMS |

Run everything with `scripts/validate_all.sh`.

Roughly 8,300 lines of source are covered by roughly 4,000 lines of tests.

## Test coverage by subsystem

| Area | Tests | What is actually exercised |
|------|-------|----------------------------|
| Project Atlas loader | 10 | Real manifests, incompatible versions, cwd independence |
| Discuss and Decision Ledger | 24 | Lifecycle, persistence across restart, ADR generation |
| Execution runtime | 20 | Transactional transitions, durable state, crash recovery |
| Atlas Harness | 12 | Attempt persistence, capability negotiation, failure paths |
| ACP | 24 | Live agent subprocess, permissions, protocol errors, MCP forwarding, terminal/file events |
| Planner and worktrees | 26 | Real git worktrees, conflict detection, parallel isolation |
| Goal execution | 15 | Plan to integrated commits, cross-provider review, budget stops |
| Verification and evidence | 24 | Gate rules, evidence persistence, DONE enforcement |
| Model routing | 25 | Role routing, live discovery and degradation, bounded fallback, durable scorecard |
| Budgets | 11 | Attempt caps, reported vs unmeasured spend |
| API | 26 | Every endpoint against the real project, path traversal, event stream |
| MCP registry | 16 | Role allowlists, read-only planning roles, refused literal secrets |
| ACP event normalization | 16 | Terminal, file, plan and tool updates; redaction at the boundary |
| Faults and security | 15 | Security guard, redaction, refused git operations |
| Fault injection (real runs) | 9 | Timeout, process kill, malformed output, disconnect, conflict, recovery |
| Performance budgets | 3 | Event append and polled endpoints, measured against the documented budgets |
| Dogfooding | 14 | Three project categories built from scratch and run end to end, plus fresh install and restart |
| Release artefacts | 9 | SBOM generation from all three lockfiles, ordering, completeness |
| Desktop (TypeScript) | 46 | API client, Tauri bridge, agent stream, tab keyboard model, WCAG contrast |

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
10. **`SecurityGuard.redact_secrets` was never called.** Redaction existed as a function and nothing invoked it, so agent output reached transcripts, attempt errors and the event stream unfiltered. It is now applied at the runner boundary, and custom patterns add to the built-in set rather than replacing it.
11. **The AG-UI namespace list did not match the backend.** It allowed `atlas.goal`/`atlas.evidence`, which are never emitted, and rejected `atlas.run`, `atlas.attempt`, `atlas.gate` and `atlas.state`, which are.
12. **The desktop crate could not compile.** `tauri` was declared with `default-features = false`, leaving `tauri::Builder` with no runtime to resolve to. Nothing had ever built it.
13. **The desktop had no Content Security Policy** (`csp: null`), and no capabilities file, so the Tauri 2 permission system granted nothing.
14. **`validate_git_command` forbade `commit` and `merge`** — the operations the runtime exists to perform — and was never called. It now refuses publishing and history rewriting, and every git call in the runtime passes through it.
15. **Two status colours failed WCAG AA.** Amber `PENDING` and green `SUCCEEDED` badges were below 4.5:1 on white, and success and failure had nearly identical luminance, making them indistinguishable in grayscale.
16. **The project id was hardcoded to `atlas-flow`** in five places, so every run against another project was misattributed in its own event log.
17. **The project root was resolved by walking up from the installed package.** An installed Atlas Flow would have found its own source tree and served its own Goals to somebody else's project.

## Findings from the independent review (2026-08-11)

A different model reviewed the work and **failed all eleven Goals**. What it found, and what happened:

18. **The gates could not be run at all.** The reviewer's environment could not import `atlas_flow`/`aiosqlite` and could not execute the tool binaries — a checkout on a `noexec` filesystem, which the repository did nothing to accommodate or even name. `scripts/bootstrap.sh` now builds a working environment regardless, and `scripts/run_gates.sh` runs every gate through one command.
19. **CI was Linux-only**, had no `cargo build`/`cargo test`, and audited no dependencies. All three are fixed; the audit immediately found **PYSEC-2026-1845** in pytest 8.4.2, now on 9.x.
20. **The desktop shell had no tests.** `cargo test` ran zero of them, which made adding it to CI meaningless. It has 9 now, over the argv parsing, project-root resolution and process-liveness logic.
21. **Windows and macOS bundles were unconfigured** — no targets, no `.ico`/`.icns`. Both are configured and the icons are generated by a script rather than committed as opaque blobs.
22. **ACP did not resume a session after a restart.** It does now, with a stale id treated as a reason to open a new session rather than to fail.
23. **`tests/e2e` contained only a `.gitkeep`** — a directory pretending to be a test suite. It is gone, replaced by an axe-core audit that runs.

## Known gaps

These are tracked in the Goal files, not hidden:

- **Models are reached only through Command Code.** There is no provider SDK and there will not be one (ADR-012). If `cmd` is absent, discovery degrades to the policy roster and the CLI and ACP runners are the only paths that perform work.
- **Adaptive scoring is post-MVP.** The scorecard is fed and persisted, but routing order is still the deterministic policy order; it does not yet reorder candidates by observed success (RFC-001).
- **Only the Linux `deb` bundle is verified.** Windows and macOS targets are configured but unbuilt; AppImage needs FUSE and a build-time download the machine did not have (P06, P09).
- **No screen-reader walkthrough.** Automated rules catch structure, not whether the result is comprehensible when read aloud (P09).
- **Release artefacts are unsigned.** This needs a key and a mechanism the project owner chooses (P10).
- **The review gate is FAILED on every Goal.** The 2026-08-11 review failed all eleven; its findings are addressed, but closing a finding does not reopen the gate — that takes another review (P00–P10).

## How to run

```sh
# Backend
uv run --project backend uvicorn atlas_flow.api.app:create_app --factory

# Frontend (separate terminal)
pnpm --filter @atlas-flow/desktop dev
```

Open http://localhost:1420. The Plan tab lists the Goals in Git; starting one
executes it and switches to Build, which follows the run live.

To open a different project, set `ATLAS_FLOW_PROJECT_ROOT`. See
[Getting Started](docs/06-user-guide/GETTING_STARTED.md).
