# Data Models

Use C# `record` types for the domain model, separate from any persistence type.
The domain projects reference no database and no serializer: a Goal that cannot
be expressed without SQLite is a Goal type that is wrong.

- DiscussionDecision: id, discussion, status, statement, rationale, provenance, impacts.
- Run: project, Goal id/revision, state, autonomy, timestamps.
- Task: objective, dependencies, role, risk, scope, state.
- RouteDecision: candidates, selected, reason, constraints.
- Attempt: task, runner, model/provider, session ref, state.
- Plan: Goal revision, task graph, autonomy, integration target and the
  optional bounded `ContextPlan` captured at creation time.
- Evidence: Goal/task, type, path/URI, digest, gate.
- ContextPlan: profile, bounded input/output budget, retrieval strategy, mode,
  reasons and recursion policy. It is a decision contract, not a copied context
  payload.
- TaskReport: task status, components, token usage, honest cost provenance,
  tests, documentation, debt and evidence pointers.
- ProjectIntelligenceSnapshot: versioned aggregate plus compact task reports;
  raw traces remain operational state.

The current Plan/Run slice uses one compact `TaskReport` per reviewed plan.
Its lifecycle is `planned → running → success|failed|blocked|cancelled`;
SQLite events remain the detailed operational record and no unobserved cost is
invented.
