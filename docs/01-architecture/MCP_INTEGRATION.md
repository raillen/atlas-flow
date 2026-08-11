# MCP Integration

MCP connects agents to external tools and data — GitHub, issue trackers,
databases, browsers and test systems, documentation systems. MCP does not
replace ACP: ACP is how Atlas Flow talks to an agent, MCP is what that agent can
reach once it is running.

Implementation: `backend/atlas_flow/mcp/registry.py`, forwarded by
`AcpRunner` in the `session/new` handshake.

## The registry is a security boundary

An agent can only use a server the client handed it, so every rule about what
an agent may touch is a rule in the registry.

| Rule | Behaviour |
| --- | --- |
| Explicit servers | Nothing is discovered or inferred. A server is forwarded only because `.ai/orchestration/mcp-servers.yaml` declares it. |
| Opt-in | Forwarding is off unless `mcp_enabled` is true. |
| Per-role allowlists | A server may name the roles it serves; other roles never see it. |
| Read-only for planning | `goal-planner`, `chief-architect` and `repo-explorer` receive only servers marked `read_only: true`. |
| Secrets outside the repository | Environment values are references (`from_env`), never literals. A declaration carrying a literal `value` is refused. |

A server that breaks a rule is **skipped with a recorded reason**, not silently
dropped. `McpRegistry.explain(role)` renders what a role received and what was
left out; the ACP runner attaches it to the attempt's evidence, so an agent
that worked without a tool it expected leaves a trail explaining why.

Refusing a literal secret rather than reading it is deliberate. A secret
committed to Git is already leaked, and quietly accepting one would make the
rule advisory.

## Configuration

```yaml
# .ai/orchestration/mcp-servers.yaml
enabled: true
servers:
  - name: docs
    command: mcp-docs
    args: ["--stdio"]
    read_only: true
  - name: github
    command: mcp-github
    roles: [core-implementer, tester]
    env:
      - name: GITHUB_TOKEN
        from_env: ATLAS_GITHUB_TOKEN
```

`mcp_servers` in configuration is a further allowlist by name: when it is
non-empty, only the servers it names are forwarded, whatever the file declares.

## Destructive calls

MCP tool calls that mutate anything still travel through the ACP permission
round-trip, which denies by default (see
[ACP Integration](ACP_INTEGRATION.md)). The registry decides *which* servers
exist for a role; permissions decide whether a specific call is allowed. Both
outcomes are recorded on the attempt.

## Not yet implemented

HTTP/SSE MCP transports — only stdio servers are described. Per-tool
allowlisting within a server, and a settings UI for editing the registry.
