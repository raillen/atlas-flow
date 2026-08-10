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

`database_path` resolves to `<project_root>/<state_dir>/<database_file>`. The
directory is created with a self-ignoring `.gitignore`, so operational state never
appears in the working repository.

## Environment overrides

| Variable | Setting |
|----------|---------|
| `ATLAS_FLOW_MAX_PARALLEL` | `max_parallel_tasks` |
| `ATLAS_FLOW_MAX_RETRIES` | `max_retries_per_task` |
| `ATLAS_FLOW_LOG_LEVEL` | `log_level` |
| `ATLAS_FLOW_AUTONOMY` | `autonomy_mode` |
| `ATLAS_FLOW_STATE_DIR` | `state_dir` |

## Not yet enforced

Budget limits (`max_cost_per_run_usd`, `max_tokens_per_run`) are configurable and
read, but nothing stops a run that exceeds them — there is no model invocation to
meter yet.
