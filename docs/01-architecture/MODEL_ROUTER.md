# Model Router

The router answers one question per task — *which model does this work, and
why* — and records the answer so it can be audited after the fact.

Models are reached through Command Code (ADR-012), never through a provider
SDK. The router selects identifiers; the harness invokes them. That is what
keeps the runtime provider-agnostic.

Implementation: `backend/atlas_flow/routing/` (`router.py`, `discovery.py`,
`store.py`) and `backend/atlas_flow/execution/budget.py`.

## Roster

Declared in `.ai/orchestration/model-policy.yaml` and mirrored by
`ModelRouter.ROSTER`:

| Model | Provider | Used for | Availability |
| --- | --- | --- | --- |
| `deepseek/deepseek-v4-pro` | deepseek | architecture, reasoning, hard debugging, security | expected |
| `xiaomi/mimo-v2.5-pro` | xiaomi | long-context implementation, refactors, integration | expected |
| `gpt-5.6-luna` | openai | efficient exploration, tests, docs, bulk work | probe-required |

Roles map to an ordered preference list (`ModelRouter.ROLE_DEFAULTS`). Routing
is deterministic: the first reachable model in the role's list wins, and
`why_this_model()` explains the choice including its index in that order. The
router does not route outside a role's list — a role whose preferred models are
all unreachable reports no selection rather than silently substituting one.

## Runtime discovery

`discover_models()` runs `cmd --list-models` and parses the identifiers out of
its output. The result has three states, and the difference matters to anyone
reading the Review screen:

| State | Meaning |
| --- | --- |
| `pending` | The probe has not answered yet. Routing uses the policy roster. |
| `reachable` | The live registry answered; only the models it listed are routable. |
| `degraded` | The probe failed — missing binary, non-zero exit, or timeout. Routing falls back to the policy roster and says so. |

A failed probe is never fatal. `pending` is never reported as `degraded`:
nothing has failed while the answer is still outstanding.

`ModelRegistry` owns the probe. It never blocks startup — the API starts a
background probe during its lifespan and cancels it on shutdown — and caches
the result for the life of the process, since the set of models a harness
exposes does not change under a running application. `ModelRegistry.seed()`
installs a result without probing, which is how tests avoid spawning `cmd`.

## Bounded fallback

When a model fails a task, `GoalRunner` retries on the next candidate for that
role. Fallback is bounded twice over:

- by `max_fallback_attempts` in configuration, and
- by the number of models that are actually reachable — an unreachable model is
  not a fallback, and retrying it just burns an attempt.

When no model is reachable at all, the harness runs on its own default model:
the runner may still be able to work without the router picking for it.

## Cross-provider review

A task marked `high` risk is reviewed by a model from a *different* provider
than the one that implemented it (`select_high_risk_reviewer`). Two models from
one provider share their training and their blind spots, so a same-provider
review adds little.

- The review runs **before** integration. Work a reviewer rejects never reaches
  the target branch; the task fails instead.
- A rejected review fails the task and records `FAILED` evidence on the
  `review` gate.
- When no other provider is reachable, or the budget is spent, the task is not
  blocked — the policy says cross-provider review *when possible* — but the
  `review` gate records `PENDING` evidence with the reason. Unreviewed work is
  never recorded as reviewed.

## Budgets

`BudgetLedger` enforces what can honestly be enforced (see
`execution/budget.py`):

- **Attempts** are always countable, so the attempt cap always applies. It is
  derived from the plan size and `max_retries_per_task`, and it is what
  actually stops a runaway retry loop.
- **Tokens and cost** are enforced only for usage a runner reports, read from
  `RunnerResult.evidence`. A run whose runner reports nothing is not assumed to
  be free: the ledger counts those as `unmeasured_attempts` and reports
  `spend_is_measured: false`, so no one can claim a run stayed inside a token
  budget nobody measured.

A limit of `0` means that dimension is not configured. Only the attempt cap is
unconditional.

## Scorecard and durable memory

Every attempt — implementation and review alike — is observed: model, role,
success, latency, run and task. Observations go to `model_observations` and are
aggregated by `RoutingStore.stats()`; route decisions with their candidate list
and reason go to `route_decisions`.

`RoutingStore.restore()` seeds a fresh `ModelScorecard` from those observations
at startup. A scorecard that resets on every restart cannot influence anything,
so the point of observing outcomes is that tomorrow's routing knows what
happened today. Adaptive *scoring* (using the scorecard to reorder candidates)
remains post-MVP — see
[RFC-001](../08-rfcs/RFC-001-ADAPTIVE-MODEL-ROUTING.md).

## API surface

- `GET /api/routing` — registry state, per-role selection with its explanation,
  and aggregated model statistics.
- `GET /api/runs/{run_id}/routing` — why each task in a run got its model.

Both are rendered on the Review screen (`apps/desktop/src/screens/ReviewScreen.tsx`).
