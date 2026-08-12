# API Contracts

> **Historical reference.** The C# desktop uses the in-process contracts under
> `src/AtlasFlow.Application/Contracts`; there is no REST server in this port.
> The route list below preserves the previous protocol mapping and is not a
> claim that these HTTP endpoints are currently available.

The local backend serves the desktop client over HTTP plus one WebSocket. JSON
uses `snake_case`; the client converts fields to `camelCase` at its boundary.
Errors use `{"detail": "..."}`. `404` means missing resource; `409` means the
resource exists but its current state/capability forbids the operation.

## Project and inspection

- `GET /healthz` — liveness and version.
- `GET /api/project` — project summary and detected mode.
- `GET /api/project/inspection` — mode, framework, Git, missing/invalid
  manifests, recommendation and capabilities.
- `GET /api/project/files` — bounded, read-only text/binary file index; ignores
  `.git`, `.atlas-flow`, dependency and build directories.
- `GET /api/project/files/{path}` — bounded text preview; traversal and binary
  content are refused.
- `POST /api/project/adaptation/preview` — non-writing scaffold preview.
- `POST /api/project/adaptation/apply` — creates only explicitly selected new
  preview paths; never overwrites; returns written paths and fresh inspection.

A project may always be explored and discussed. `can_plan`, `can_run` and
`can_review` come from the inspection contract; external projects receive an
explicit `409` when they call a gated operation.

## Goals and verification

- `GET /api/goals` — every Goal declared in Git, or an empty list while the
  project is not executable.
- `GET /api/goals/{goal_id}`
- `GET /api/goals/{goal_id}/verification` — gate verdicts, evidence and
  completion blocking reason.

## Plans and runs

- `POST /api/goals/{goal_id}/plans` — creates a `DRAFT` plan snapshot.
- `GET /api/goals/{goal_id}/plans` — plan history.
- `GET /api/plans/{plan_id}`
- `POST /api/plans/{plan_id}/lock` — transitions a draft once to `LOCKED`.
- `POST /api/runs` — accepts `plan_id`; when supplied, only a matching locked
  snapshot can execute, and it becomes `CONSUMED` after scheduling.
- `GET /api/runs` — newest first.
- `GET /api/runs/{run_id}` — run, tasks, attempts and events.
- `GET /api/runs/{run_id}/events`
- `POST /api/runs/{run_id}/cancel` — cooperative cancellation, with `409` after
  the state machine reaches a non-cancellable phase.

A legacy request without `plan_id` remains temporarily accepted for migration,
but the desktop workspace always uses create → review → lock → run.

## Routing and Discuss

- `GET /api/routing`
- `GET /api/runs/{run_id}/routing`
- `GET/POST /api/discussions`
- `GET /api/discussions/{session_id}`
- `POST /api/discussions/{session_id}/messages`
- `POST /api/discussions/{session_id}/decisions`
- `POST /api/discussions/{session_id}/decisions/{decision_id}/accept`
- `POST /api/discussions/{session_id}/finalize` — available only after the
  project is Atlas ready.

## Settings

- `GET /api/settings` — the settings document: every known setting with its
  effective value, source (default/project/user/environment), owning scope and
  restart requirement; model providers with credential state; MCP status; and
  runtime diagnostics.
- `POST /api/settings/validate` — dry run: validates a `{scope, values}` patch
  without writing anything. `422` on unknown keys, values of the wrong kind, or
  keys the scope cannot own; `409` (as `422`) when a value is controlled by an
  environment variable.
- `PUT /api/settings` — applies a `{scope, values}` patch to the file owning
  that scope (`.ai/orchestration/settings.yaml` for project scope, `~/.atlas-flow.yaml`
  for user scope). Returns the refreshed document plus `changed`,
  `restart_required` and `restart_reason`.
- `POST /api/settings/reset` — removes the given keys from the scope's file,
  returning the refreshed document.

A setting is read from the closest source that defines it: default → project →
user → environment. Project-scope settings live in the project's
`.ai/orchestration/settings.yaml`; user-scope settings in `~/.atlas-flow.yaml`.
Credentials are never written by this API — providers report only whether their
referenced environment variable is set.

## Documentation

- `GET /api/docs`
- `GET /api/docs/{path}` — Markdown confined to `docs/`.

## Streaming

`WS /ws/{session_id}` carries AG-UI envelopes. Durable domain events are
broadcast as committed; live agent narration is not persisted.
