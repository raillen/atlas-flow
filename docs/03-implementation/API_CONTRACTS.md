# API Contracts

The local backend serves the desktop client over HTTP plus one WebSocket. Every
endpoint reads real state: Goals and documentation come from Git, runs and
evidence come from the operational database.

## Wire conventions

Requests and responses are JSON with `snake_case` fields; the client converts to
`camelCase` at its boundary. Event payloads are passed through untouched, since
they round-trip to the backend.

Errors use the FastAPI `{"detail": "..."}` shape. `404` means the resource does
not exist; `409` means it exists but its current state forbids the operation.

## Endpoints

### Project
- `GET /healthz` — liveness and version.
- `GET /api/project` — project id, registries, registered runners.
- `GET /api/config` — effective configuration, including the resolved database path.

### Goals
- `GET /api/goals` — every Goal declared in Git.
- `GET /api/goals/{goal_id}`
- `GET /api/goals/{goal_id}/verification` — gate verdicts, attached evidence, and
  whether the Goal may be completed. `blocking` explains why not.

### Runs
- `GET /api/runs` — newest first.
- `POST /api/runs` — start a Goal. Returns `202` as soon as the run is scheduled;
  execution continues in the background and is followed through the event stream.
- `GET /api/runs/{run_id}` — run, tasks, attempts and events.
- `GET /api/runs/{run_id}/events`

### Discuss
- `GET /api/discussions`, `POST /api/discussions`
- `GET /api/discussions/{session_id}`
- `POST /api/discussions/{session_id}/messages`
- `POST /api/discussions/{session_id}/decisions`
- `POST /api/discussions/{session_id}/decisions/{decision_id}/accept`
- `POST /api/discussions/{session_id}/finalize` — writes ADRs and the Decision
  Ledger into `docs/`. Returns `409` when the draft is not complete, and refuses
  to overwrite existing files unless `overwrite=true`.

### Documentation
- `GET /api/docs` — canonical documents grouped by section.
- `GET /api/docs/{path}` — Markdown content. Paths are confined to `docs/`;
  anything resolving outside it, or not ending in `.md`, is a `404`.

## Streaming

`WS /ws/{session_id}` carries AG-UI envelopes: `{type, timestamp, payload}`.
Every domain event committed by the runtime is broadcast to connected clients as
it lands, so the desktop follows a run rather than polling it.

## Not yet implemented

Versioning under `/api/v1`, pause/resume/cancel of a running Goal, Goal amendment
transitions, and Settings endpoints for runners, budgets, permissions and MCP.
