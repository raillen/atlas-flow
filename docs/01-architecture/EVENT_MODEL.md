# Event Model

Every event carries an id, a timestamp, its project and run, a type, a version
and a payload. Two streams share that envelope but not their guarantees.

## Durable domain events

Written inside the same transaction as the state change they describe, so an
event log can never disagree with the state it explains
(`backend/atlas_flow/execution/models.py`).

| Type | Meaning |
| --- | --- |
| `atlas.run.started` / `.completed` / `.failed` | Run lifecycle |
| `atlas.task.ready` / `.succeeded` / `.failed` | Task lifecycle |
| `atlas.attempt.started` / `.completed` / `.failed` | One model invocation |
| `atlas.gate.passed` / `.failed` | Verification outcome |
| `atlas.state.change` | Any other transition, carrying `previous` and `next` |

These are persisted, replayed on recovery, and broadcast to connected clients as
they commit.

## Live agent narration

Normalized from ACP `session/update` notifications
(`backend/atlas_flow/acp/events.py`) and broadcast over AG-UI:
`atlas.agent.message`, `atlas.agent.thought`, `atlas.terminal.output`,
`atlas.file.changed`, `atlas.tool.call`, `atlas.plan.updated`.

Narration is **not persisted**. It is volume — terminal chunks and thoughts —
and storing every one of them would bury the audit trail rather than enrich it.
The durable record of what an attempt did is its transcript and its evidence.

See [ACP Integration](ACP_INTEGRATION.md) for how each kind is recognized.

## Redaction

Agent-produced text is redacted at the runner boundary — normalized ACP updates
and every `RunnerResult` — before it can reach a transcript, an attempt error, a
stored event or a client. Redaction is unconditional; `redaction_patterns` adds
project-specific patterns to the built-in set rather than replacing it. See
[Configuration](../03-implementation/CONFIGURATION.md#logging-and-redaction).
