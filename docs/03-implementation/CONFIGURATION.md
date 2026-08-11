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

## Budgets

| Key | Default | Meaning |
|-----|---------|---------|
| `max_retries_per_task` | `2` | Retries per task. With the plan size, this derives the run's hard attempt cap. |
| `max_fallback_attempts` | `2` | How far down a role's candidate list a failing task may fall back. |
| `max_tokens_per_run` | `1000000` | Token ceiling, enforced against reported usage. `0` disables it. |
| `max_cost_per_run_usd` | `10.0` | Cost ceiling, enforced against reported usage. `0` disables it. |

The attempt cap is unconditional, since attempts are always countable. Tokens
and cost are enforced only for usage a runner actually reports; a run whose
runner reports nothing is recorded as having unmeasured spend rather than being
assumed free. See [Model Router](../01-architecture/MODEL_ROUTER.md#budgets).
