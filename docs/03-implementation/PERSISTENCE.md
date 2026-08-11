# Persistence

## Git — canonical

Project Atlas docs, Goals, ADR/RFC, model policy, manifests, selected
Skills/Agents/Recipes and accepted Decisions. A Goal reaching DONE is a commit to
its Goal file, never a row in SQLite.

## SQLite — operational

Everything that describes operational work: discussions, runs, tasks, attempts,
the append-only event log, gate evidence and reviewable plan snapshots.

The database lives at `<project>/.atlas-flow/state.db`. `.atlas-flow/` writes its
own `.gitignore` and never becomes canonical project content.

## Plan snapshots

A plan is stored as `DRAFT`, `LOCKED` or `CONSUMED`:

- `DRAFT` can be replaced while the person reviews it;
- `LOCKED` is the exact plan approved for execution and is immutable;
- `CONSUMED` records that a run was scheduled from it.

A locked snapshot stores Goal id/revision, autonomy, runner, integration target
and task contracts. A run must match the current Goal revision and settings.
Changing the Goal requires a new plan rather than silently mutating history.

Schema creation is additive and idempotent. Existing run/discussion state is not
discarded when plans are introduced.

## External projects

Opening an external project does not create operational state in canonical docs.
The inspection report is derived from the filesystem; adaptation writes only
explicitly authorized new files. No Goal is synthesized as locked or complete.

## Transactional guarantee

A state change and its event are written in one transaction. Recovery reconstructs
what happened from the event log, and invalid transitions are rejected before
anything is written.
