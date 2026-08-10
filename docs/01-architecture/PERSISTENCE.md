# Persistence

## Git — canonical

Project Atlas docs, Goals, ADR/RFC, model policy, manifests, selected
Skills/Agents/Recipes, accepted Decisions. A Goal reaching DONE is a commit to
its Goal file, never a row in the database.

## SQLite — operational

Everything that describes an execution in progress: discussions and their
Decision Ledger, runs, tasks, attempts, the append-only event log, and gate
evidence.

The database lives at `<project>/.atlas-flow/state.db` by default, resolved from
`AtlasFlowConfig.database_path`. It is file-backed so run state survives a crash
or restart; an in-memory database is available for tests that do not need
durability, and is never the default.

`.atlas-flow/` writes its own `.gitignore` containing `*` when created. Atlas
Flow works inside other people's repositories, and its bookkeeping must not
appear in their `git status` — nor trip its own dirty-tree checks before
integrating a task.

### Transactional guarantee

A state change and the event that explains it are written in a single
transaction. Recovery reconstructs what happened from the event log, so a state
the log cannot account for is not a state the system is allowed to reach.
Invalid transitions are rejected before anything is written.

### Schema

`SCHEMA_VERSION` is recorded in the `schema_version` table. Tables are created
idempotently; numbered migrations are not yet implemented, so a schema change
currently requires discarding operational state.
