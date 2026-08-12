# Roadmap

- **P00 Foundation** — repo, CI, Atlas contract, conventions.
- **P01 Project Atlas Integration** — manifests, registries, Goals.
- **P02 Discuss & Project Draft** — chat state, Decision Ledger, readiness/finalization.
- **P03 Orchestration Runtime** — Run/Task/Attempt, event bus, SQLite, cancellation/recovery.
- **P04 Atlas Harness** — ACP and generic CLI runner.
- **P05 Goal Planner & DAG** — planning, worktrees, safe concurrency, integration.
- **P06 Desktop UX** — Avalonia workspace shell and the six workspace stages.
- **P07 Verification & Evidence** — deterministic gates and independent review.
- **P08 Routing & Intelligence** — role routing, budgets, scorecards, fallback.
- **P09 Hardening** — security, recovery, accessibility, performance, packaging.
- **P10 Beta / 1.0** — dogfood across at least three materially different project categories.

## C# port — remaining work

The original phases above preserve the product history. The active C# work is
decomposed into executable Goals in
[REMAINING_GOALS.md](../03-implementation/REMAINING_GOALS.md):

- **P13** — re-establish C# CI, evidence, review and release gates;
- **P14–P16** — Project Atlas v2 schemas/graph, documentation service and context/impact;
- **P17–P20** — lifecycle verification, runners/protocols, routing/settings and AG-UI runtime events;
- **P21–P23** — complete Avalonia surfaces, hardening and the C# CLI;
- **P24** — packaging, compatibility, dogfooding and 1.0;
- **P25** — optional post-MVP retrieval/intelligence extensions, currently `DRAFT`.
