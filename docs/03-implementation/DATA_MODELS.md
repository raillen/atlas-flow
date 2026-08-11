# Data Models

Use C# `record` types for the domain model, separate from any persistence type.
The domain projects reference no database and no serializer: a Goal that cannot
be expressed without SQLite is a Goal type that is wrong.

- DiscussionDecision: id, discussion, status, statement, rationale, provenance, impacts.
- Run: project, Goal id/revision, state, autonomy, timestamps.
- Task: objective, dependencies, role, risk, scope, state.
- RouteDecision: candidates, selected, reason, constraints.
- Attempt: task, runner, model/provider, session ref, state.
- Evidence: Goal/task, type, path/URI, digest, gate.
