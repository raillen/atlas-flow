# Data Models

Use typed Pydantic/domain models separate from ORM.

- DiscussionDecision: id, discussion, status, statement, rationale, provenance, impacts.
- Run: project, Goal id/revision, state, autonomy, timestamps.
- Task: objective, dependencies, role, risk, scope, state.
- RouteDecision: candidates, selected, reason, constraints.
- Attempt: task, runner, model/provider, session ref, state.
- Evidence: Goal/task, type, path/URI, digest, gate.
