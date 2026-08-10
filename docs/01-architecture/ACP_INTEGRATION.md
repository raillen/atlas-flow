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

## Not yet implemented

MCP server forwarding through ACP, terminal and file event streaming, and
session resumption across process restarts.
