# Validation Report

Generated: 2026-08-10

## Automated checks

| Check | Command | Result |
|-------|---------|--------|
| Python lint | `uv run --project backend ruff check .` | PASS |
| Python types | `uv run --project backend mypy` | PASS (strict, 56 files) |
| Python tests | `uv run --project backend pytest` | PASS — 356 tests |
| TypeScript build | `pnpm run typecheck` | PASS |
| JS lint | `pnpm run lint` | PASS |
| JS tests | `pnpm run test` | PASS — 78 tests, including an axe-core DOM audit |
| Docs links | `python scripts/validate_docs.py` | PASS |
| Goal contracts | `python scripts/validate_goals.py` | PASS — 11 Goals, 11 DONE with evidence |
| Command Code | `scripts/validate_command_code.sh` | PASS — 9 agents, 15 skills |
| Desktop shell | `cargo fmt`, `clippy -D warnings`, `cargo test` | PASS — 16 tests |
| Dependency audit | `sh scripts/audit_dependencies.sh` | PASS — no vulnerabilities; 17 unmaintained-crate warnings from Tauri's GTK3 chain |
| Packaging | `sh scripts/package_smoke.sh` | PASS — deb and AppImage, SBOM (840 components), SHA256SUMS, GPG signature verified from a clean keyring |
| Packaged app | `sh scripts/e2e_packaged.sh` | PASS — drives the real AppImage: starts a backend, serves the right project |
| Every gate at once | `sh scripts/bootstrap.sh && sh scripts/run_gates.sh` | PASS — 12 gates |

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

## Findings from the second review (2026-08-11)

The re-review moved all eleven Goals from FAILED to PARTIAL, and found three more things:

24. **The accessibility suite failed with `React.act is not a function`** on any machine with `NODE_ENV=production` in its environment: React resolves a different build per `NODE_ENV`, and the production build does not export `act`. Pinned in `vitest.config.ts` — a `VAR=value` shell prefix would have fixed POSIX and broken the Windows CI job that had just been added.
25. **The AppImage was unbuildable, not merely unverified.** `linuxdeploy` is itself an AppImage and mounting one needs FUSE. `APPIMAGE_EXTRACT_AND_RUN=1` removes that requirement; the bundle now builds, and the smoke test unpacks it and checks the executable is inside rather than trusting the file name.
26. **`GET /api/goals` re-parsed every Goal on every request** — ~47 ms idle, **253 ms on a loaded machine**, over its own 150 ms budget. Found by running the suite while the machine was busy, which is the only way a budget measured on an idle machine means anything. The loader now caches per project root and invalidates on the file signature: ~5 ms, and an edit is still seen immediately.

## Findings from the self-review (2026-08-11)

The owner waived model diversity and undertook a second reading of their own. The self-review found two defects, both reproduced before being fixed; the write-up and its limitations are at `docs/07-decisions/reviews/2026-08-11-self-review.md`.

27. **A failing review satisfied the review gate.** `check_declared_evidence` counted any truthy evidence value as coverage, so a Goal carrying `review: "FAILED — the reviewer rejected this"` was reported completable. Live at the time: all eleven Goals carried `review: "PARTIAL — ..."`, so the validator would have accepted DONE on every one of them. An entry opening with a non-passing verdict is now reported as *failing* rather than as covering its gate.
28. **Parallel tasks overspent the attempt budget.** The check and the accounting straddled the `await` where the model runs, so every concurrent task passed the same check before any had counted itself. Reproduced: a cap of one bought four attempts. Reservation and accounting are separate now, and a crash between them keeps the slot spent rather than releasing it.

## Findings from using the packaged application (2026-08-11)

Three defects reached a build that twelve gates called green, and a fourth got past the accessibility suite. Each lived where a whole layer is blind, not in a gap more tests of the same shape would close.

29. **A dead backend was reported as RUNNING.** Spawning succeeds for a command that dies immediately, so the shell claimed success it had not checked. It waits and confirms now, and returns the exit status with the last lines of the log.
30. **The backend's output went to `/dev/null`**, so a failure left nothing to diagnose. It goes to `/tmp/atlas-flow-backend.log`, and the UI shows the path.
31. **A packaged app cannot trust its own environment.** An AppImage runs with its working directory inside its own mount and points `PYTHONHOME` and `LD_LIBRARY_PATH` at itself, so the shell reported the bundle as the project root and the backend it launched inherited an environment that killed it. The bundle is refused as a project root, and every variable naming it is stripped from the child.
32. **Arrow-key navigation between tabs moved exactly once.** Focus was set inside the key handler, onto a tab whose `tabIndex` was still `-1` and under a panel being replaced. jsdom does not reproduce it; only driving the real webview does.

## Findings from closing the remaining gaps (2026-08-11)

33. **A run could not be cancelled.** `RunState.CANCELLED`, `Harness.cancel_task` and `AcpRunner.cancel` all existed and nothing called any of them. There was no endpoint and no button: a Goal spending budget could only be stopped by killing the process.
34. **`Harness._active_tasks` was declared and never filled**, so every `cancel_task` returned `False` — the mechanism that made cancellation impossible even once something did call it.
35. **The task state machine could not express cancellation.** `PLANNED` had no path to `CANCELLED`, so stopping a run before its tasks started required marking them `READY` first — a lie the machine forced on the caller — and `BLOCKED` was a dead end nothing could leave.
36. **Only the `build` gate ever got evidence during a run.** Nothing produced `tests` or `documentation`, so a Goal that Atlas Flow planned and executed could never become completable on its own; a human had to attach the rest. Planning and execution worked and verification did not close.

37. **The Discuss screen never talked to the backend.** It opened a WebSocket, echoed what you typed back at you and lost it — the Decision Ledger was implemented and tested, and the screen in front of it wrote to nothing.
38. **The Plan showed dependency layers as flat lists**, not a graph. It is drawn now, with a stage list beside it as a peer rather than a fallback.

## Known gaps

These are tracked in the Goal files, not hidden:

- **Models are reached only through Command Code.** There is no provider SDK and there will not be one (ADR-012). If `cmd` is absent, discovery degrades to the policy roster and the CLI and ACP runners are the only paths that perform work.
- **Adaptive scoring is post-MVP.** The scorecard is fed and persisted, but routing order is still the deterministic policy order; it does not yet reorder candidates by observed success (RFC-001).
- **macOS and Windows are out of scope** by an owner decision on 2026-08-11, recorded as non-goals on P06, P09 and P10. The supported platform is Linux on desktop, x86_64.
- **The screen-reader walkthrough is deferred** by the same decision. The automated rendered-DOM audit stays required and passing (P09).
- **No screen-reader walkthrough.** Automated rules catch structure, not whether the result is comprehensible when read aloud (P09).
- **The signing key has no passphrase**, so it works unattended and anyone with read access to the maintainer's home directory can sign as the project. A deliberate trade, recorded rather than hidden (P10).
- **17 unmaintained-crate warnings** from the gtk-rs GTK3 bindings Tauri 2 depends on. Reported by the audit rather than swallowed; nothing can be done from this repository.
- **The review gate was closed by a self-review**, after the owner waived the model-diversity rule and undertook a second reading of their own. It is recorded as a self-review in every Goal's evidence and written up with its own limitations at `docs/07-decisions/reviews/2026-08-11-self-review.md`. Two earlier rounds by a different model are what found most of what is listed above.

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
