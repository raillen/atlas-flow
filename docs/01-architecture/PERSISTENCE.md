# Persistence

## Git — canonical

Project Atlas docs, Goals, ADR/RFC, model policy, manifests, selected
Skills/Agents/Recipes, accepted Decisions. A Goal reaching DONE is a commit to
its Goal file, never a row in the database.

## SQLite — operational

Everything that describes an execution in progress: discussions and their
Decision Ledger projection, runs, tasks, attempts, the append-only event log,
and gate evidence.

The C# database lives at `<project>/.atlas/state.db` for legacy projects and at
`<project>/.atlas/runtime/atlas.db` when `atlas.json` is present. It is
file-backed so run state survives a crash or restart; an in-memory database is
available for tests that do not need durability, and is never the default.

Operational `.atlas` state is derived and must not replace Git truth. Atlas Flow
works inside other people's repositories, and its bookkeeping must not appear
in their `git status` — nor trip its own dirty-tree checks before integrating a
task.

### Transactional guarantee

A state change and the event that explains it are written in a single
transaction. Recovery reconstructs what happened from the event log, so a state
the log cannot account for is not a state the system is allowed to reach.
Invalid transitions are rejected before anything is written.

### Schema

`SCHEMA_VERSION` is recorded in the `schema_version` table. Base tables are
created idempotently and the current startup migration upgrades plan context
and legacy Discuss columns without discarding operational state. Fully
numbered rollback migrations remain a P22 deliverable.
