# Model Routing

Every task is routed to a model by role, and the reason is recorded. The Review
tab shows it; `GET /api/routing` and `GET /api/runs/{id}/routing` return it.

## What you see

- **Registry state** — `pending` while the live registry is being probed,
  `reachable` once it answers, `degraded` if `cmd --list-models` is missing,
  fails or times out. Degraded is not an error you have to fix: routing falls
  back to the roster in `.ai/orchestration/model-policy.yaml`, it just cannot
  confirm those models are reachable.
- **Per role** — the model selected, its provider, and a sentence explaining
  where it sat in that role's preference order.
- **Per model** — how many attempts used it, how many succeeded, and the average
  latency, accumulated across runs rather than reset on restart.

## What happens when a model fails

The task is retried on the next reachable model for that role. Fallback stops at
`max_fallback_attempts`, and at the number of models actually reachable —
retrying an unreachable model only burns an attempt.

A role whose preferred models are all unreachable reports no selection rather
than quietly substituting one from another role's list.

## High-risk work

A task marked `high` risk is reviewed by a model from a *different provider*
before its work is merged, so a rejected change never reaches your branch. If no
other provider is reachable, the task is not blocked, but the `review` gate
records PENDING: unreviewed work is never recorded as reviewed.

## Budgets

A run stops when it has spent its attempt budget, derived from the plan size and
`max_retries_per_task`. Token and cost ceilings apply to usage a runner actually
reports; if your runner reports none, the run is recorded as having unmeasured
spend rather than being assumed free.

See [Model Router](../01-architecture/MODEL_ROUTER.md) for the mechanism.
