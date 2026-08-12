# Current Project State

> **Esta branch é o porte para C# (`csharp-avalonia`).** Os estados de Goal
> abaixo descrevem a implementação Python/Tauri, que agora vive em `reference/`
> e continua sendo desenvolvida na `main`.
>
> Nenhum Goal está DONE nesta branch. O runtime mudou, e um Goal cujo gate de
> build nunca compilou não passou o gate — ver
> [RELEASE_GATES.md](docs/04-quality/RELEASE_GATES.md).
>
> P06 (Desktop Modes), P09 (Hardening) e P10 (Beta e validação 1.0) reabrem por
> [ADR-018](docs/07-decisions/ADR-018-AVALONIA-DESKTOP.md): Windows voltou ao
> escopo depois de ter sido registrado como non-goal em 2026-08-11.

**Project:** Atlas Flow
**Framework:** Project Atlas Framework 0.1.0 (runtime with v0.2 JSON, LPC/PCA and Project Intelligence compatibility)
**Status:** 11 of 13 Goals DONE; P11 and P12 active
**Current phase:** P12 active — UX foundation

The C# runtime now exposes bounded context planning, persists the selected
`ContextPlan` with each plan snapshot, and emits a compact Project Intelligence
report through the Plan/Run lifecycle. The repository remains a v0.1 canonical
project; v0.2 migration, retrieval execution, context garbage collection and
provider-level usage measurement are still separate Goals.

The Avalonia desktop now projects the persisted context decision in the Plan
inspector and the compact Project Intelligence aggregate in the context rail.
This is intentionally a decision/summary surface: retrieval payloads and
unobserved cost are not presented as if they were available to the frontend.

The Define stage now has a contract-first Discuss surface with a rehydratable
thread, composer, decision summary and project-relative file/image references.
IDiscussionService is still intentionally unregistered in this C# runtime, so
the UI reports that boundary explicitly; reference validation and persistence
remain application responsibilities.

## How to read the Goal states

Every Goal was audited on 2026-08-10 against its own acceptance criteria. Goals
that had been marked DONE without meeting them were reopened; each Goal's
`history` records what was unmet, what has since been closed, and what still
blocks it.

Every completed Goal is DONE, and that is enforced rather than asserted; P11
and P12 are the active evolution Goals:
`scripts/validate_goals.py` fails CI if a Goal declares DONE without passing
evidence for every gate it declares required — and, since 2026-08-11, evidence
that *opens with a failing verdict* no longer counts as covering its gate. That
hole was found by the review below; before it was closed, all eleven Goals
would have passed the check while carrying `review: "PARTIAL — ..."`.

| Phase | Goal | State | Blocking |
|-------|------|-------|----------|
| P00 | Repository Foundation | DONE | — |
| P01 | Project Atlas Integration | DONE | — |
| P02 | Discuss and Decision Ledger | DONE | — |
| P03 | Orchestration Runtime | DONE | — |
| P04 | Atlas Harness | DONE | — |
| P05 | Goal Planner and DAG Execution | DONE | — |
| P06 | Desktop Modes | DONE | — |
| P07 | Verification and Evidence | DONE | — |
| P08 | Routing, Budgets and Scorecards | DONE | — |
| P09 | Hardening | DONE | — |
| P10 | Beta and 1.0 Validation | DONE | — |
| P11 | Atlas Flow v2 Foundation | ACTIVE | Independent review and full Goal evidence |
| P12 | Atlas Flow UX Foundation | ACTIVE | Independent review and full Goal evidence |

Three reviews were performed on 2026-08-11. The first two were by a different
model, as the model-diversity rule required: they failed all eleven Goals, then
moved them to PARTIAL. Both rounds of findings are closed. macOS/Windows support
and the manual screen-reader walkthrough were scoped out by the owner and are
recorded as non-goals on the Goals they affected.

The third was a **self-review**, after the owner waived model diversity and
undertook to read the work independently themselves. It is recorded as a
self-review in every Goal's evidence, so nobody later mistakes it for an
independent one, and it is written up in full — including its own limitations —
at [docs/07-decisions/reviews/2026-08-11-self-review.md](docs/07-decisions/reviews/2026-08-11-self-review.md).
It found two defects, both reproduced before being fixed: a failing review
verdict counted as satisfying the review gate, and parallel tasks overspent the
attempt budget four to one.

## What works end to end

Starting a Goal from the desktop decomposes it into one task per acceptance
criterion, schedules the tasks in dependency order, runs each one in its own git
worktree through a registered runner, integrates the result, records gate
evidence and streams every state change to the UI. Run state is durable and
survives a crash.

Atlas Flow runs against whatever project it is opened on, not only this one:
three project categories — a library, a web application and a CLI — are built
from scratch and executed end to end in the test suite.

Each task is routed to a model by role. The live model registry is probed
through `cmd --list-models` in the background at startup; a failing task falls
back to another reachable model within a bounded budget, high-risk work is
reviewed by a different provider before it is integrated, and every attempt is
observed so routing memory survives a restart. Attempt caps are enforced
unconditionally; token and cost ceilings are enforced against usage a runner
actually reports, and unmeasured spend is reported as unmeasured.

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

Complete the P11 and P12 foundation reviews and then continue the remaining
AF-EVO-001 phases. The P00–P10 gates pass, the packaged AppImage runs a Goal end to end,
releases are signed and verifiable, and every completed Goal carries evidence
for all four of its gates.

What a second reader should look at hardest is the part no gate covers — whether
the work does what the Goals actually asked for, rather than whether it is
internally consistent. A self-review is good at the second and structurally weak
at the first.

Deferred by owner decision on 2026-08-11, and recorded as non-goals rather than
quietly dropped: macOS and Windows support (P06, P09, P10), and the manual
screen-reader walkthrough (P09). The supported platform is Linux on desktop.

See [Release Gates](docs/04-quality/RELEASE_GATES.md) for the gate-by-gate
status.
