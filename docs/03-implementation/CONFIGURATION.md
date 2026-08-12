# Configuration

Precedence: environment variables → user Atlas Flow settings (`~/.atlas-flow.yaml`)
→ project orchestration config (`.ai/orchestration/`) → defaults.

Only keys a source actually declares are merged; anything absent falls through to
the default rather than being looked up in a partially built layer.

Secrets never in Git; use OS keychain/secure storage or env refs.

## Domains

Autonomy, concurrency, budget, model routing, runner discovery, MCP, Git,
operational state, artifact retention, logging/redaction.

## Operational state

| Key | Default | Meaning |
|-----|---------|---------|
| `state_dir` | `.atlas-flow` | Where operational state lives, relative to the project root |
| `database_file` | `state.db` | SQLite file inside `state_dir` |

`database_path` resolves to `<project_root>/<state_dir>/<database_file>`. For a
v0.2 project with `atlas.json`, the runtime defaults to `.atlas/runtime/atlas.db`;
the v0.1 reader keeps `.atlas/state.db` for compatibility. The directory is
created with private permissions, so operational state never appears in the
working repository.

## Environment overrides

| Variable | Setting |
|----------|---------|
| `ATLAS_FLOW_MAX_PARALLEL` | `max_parallel_tasks` |
| `ATLAS_FLOW_MAX_RETRIES` | `max_retries_per_task` |
| `ATLAS_FLOW_LOG_LEVEL` | `log_level` |
| `ATLAS_FLOW_AUTONOMY` | `autonomy_mode` |
| `ATLAS_FLOW_STATE_DIR` | `state_dir` |

## Logging and redaction

| Key | Default | Meaning |
|-----|---------|---------|
| `log_level` | `INFO` | Standard logging level. |
| `redaction_patterns` | `[]` | Extra regexes added to the built-in secret patterns. |

Redaction is not a switch. Every `RunnerResult` and every normalized ACP update
is redacted at the runner boundary, because a run that may leak a token is not a
configuration preference. Project patterns are added to the built-in set, never
substituted for it — losing the defaults by declaring one custom pattern is
exactly how a redaction list becomes a leak.

## MCP

| Key | Default | Meaning |
|-----|---------|---------|
| `mcp_enabled` | `false` | Whether declared MCP servers are forwarded to agents at all. |
| `mcp_servers` | `[]` | Further allowlist by server name. Empty means "whatever the file declares". |

Servers themselves live in `.ai/orchestration/mcp-servers.yaml`. See
[MCP Integration](../01-architecture/MCP_INTEGRATION.md) for the role and
secret rules the registry enforces.

## Budgets

| Key | Default | Meaning |
|-----|---------|---------|
| `max_retries_per_task` | `2` | Retries per task. With the plan size, this derives the run's hard attempt cap. |
| `max_fallback_attempts` | `2` | How far down a role's candidate list a failing task may fall back. |
| `max_tokens_per_run` | `1000000` | Token ceiling, enforced against reported usage. `0` disables it. |
| `max_cost_per_run_usd` | `10.0` | Cost ceiling, enforced against reported usage. `0` disables it. |

For v0.2 projects, `atlas.json.context.profiles` defines the LPC/PCA context
target and hard limits, output limits, expansion rounds and delegation depth.
The selected decision is persisted with a new Plan snapshot. Plan/Run also
update the compact Project Intelligence history; retrieval, context garbage
collection and provider-level usage measurement remain separate slices.

The operational SQLite schema is currently version 4. Existing databases are
upgraded on startup with the nullable `plans.context` column, so v1 plan rows
remain readable with no context decision.

The attempt cap is unconditional, since attempts are always countable. Tokens
and cost are enforced only for usage a runner actually reports; a run whose
runner reports nothing is recorded as having unmeasured spend rather than being
assumed free. See [Model Router](../01-architecture/MODEL_ROUTER.md#budgets).
