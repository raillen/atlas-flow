# ACP Integration

ACP is preferred between Atlas Harness and compatible coding agents. Atlas Flow
acts as the ACP client.

## Transport

JSON-RPC 2.0 over newline-delimited stdio against an agent subprocess. The
connection is bidirectional: Atlas Flow calls the agent, and the agent calls back
for decisions only the client can make. Both directions share one pair of pipes,
so messages are routed by shape rather than by assuming strict request/response
alternation.

Non-JSON lines on stdout are skipped rather than treated as protocol errors —
agents write diagnostics there, and killing a live session over a log line would
be worse than ignoring it.

## Lifecycle

`initialize` negotiates the protocol version and capabilities, then
`session/new` opens a session and `session/prompt` runs a turn while
`session/update` notifications stream progress.

An agent advertising a protocol version newer than this client supports is
rejected with a clear error. Optional capabilities degrade instead of failing:
`session/load` is only attempted when the agent advertised `loadSession`, and
returns `False` otherwise rather than raising.

## Permissions

`session/request_permission` is surfaced to a policy that decides per request.
**The default policy denies everything.** Silently granting whatever an agent
asks for would make the permission round-trip decorative, so a looser policy is
opted into deliberately — `allow_read_only` permits only non-mutating tool kinds.

A task whose agent was denied permission is reported as failed, with the denied
tools named, rather than being recorded as a success that quietly did less.

## Capability negotiation

`AcpRunner` advertises what the transport supports, then drops the capabilities
the connected agent turns out not to offer. The Harness refuses to run a task on
a runner that cannot satisfy the capabilities that task requires, and can select
a capable runner from those registered.

## MCP forwarding

`session/new` carries the MCP servers the task's role is allowed to reach. The
client decides, never the agent: an agent can only use a server it was handed.
See [MCP Integration](MCP_INTEGRATION.md) for the rules the registry enforces.
What a role received, and what was skipped and why, is attached to the attempt
as evidence.

## Terminal and file events

`session/update` notifications are normalized into a small closed vocabulary
(`backend/atlas_flow/acp/events.py`) so nothing downstream has to learn one
agent's wire dialect:

| Kind | AG-UI event | Source |
| --- | --- | --- |
| message | `atlas.agent.message` | `agent_message_chunk`, `user_message_chunk` |
| thought | `atlas.agent.thought` | `agent_thought_chunk` |
| terminal | `atlas.terminal.output` | tool calls of kind `execute`, or any call carrying a `terminal` content block |
| file | `atlas.file.changed` | tool calls of kind `edit`/`write`/`delete`, or any call carrying `diff` blocks |
| tool | `atlas.tool.call` | any other named tool call |
| plan | `atlas.plan.updated` | `plan` |

An update the normalizer does not recognize is kept in the raw update list for
debugging but is **not** published — forwarding an untyped blob would put one
agent's vocabulary into every consumer downstream.

Narration is broadcast live and **not persisted**. A run's durable history is
its domain event log; terminal chunks and thoughts are volume, and storing every
one of them would bury the audit trail rather than enrich it. What does persist
is the outcome: terminal output is folded into the attempt's transcript under a
`--- terminal ---` marker, and the files the agent says it changed are recorded
as attempt evidence so a reviewer can check the claim against the worktree.

## Session resumption

An agent session holds everything the agent has read and concluded. Losing it
to a restart means the next attempt re-derives what it already knew, and the
user pays for that twice — so the session id is stored per task and runner
(`backend/atlas_flow/acp/store.py`) and `session/load` is attempted before
`session/new`.

Three ways resumption legitimately does not happen, none of them a failure:
nothing was stored, the agent does not advertise `loadSession`, or the agent no
longer recognizes the id. All three mean "open a new session"; a stale id is
forgotten so the next attempt does not retry it. Every attempt records
`session: resumed | new` as evidence, so a resumed attempt is distinguishable
from one that started cold.

Only the identifier is stored. The conversation itself stays in the agent.

## Registering an agent

No ACP runner is registered unless `acp_agent_command` is configured (or
`ATLAS_FLOW_ACP_AGENT` is set) — there is no sensible default agent to guess
at, and a runner that cannot start is worse than one that is absent.

## Not yet implemented

HTTP/SSE MCP transports.
