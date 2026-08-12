# Project Orchestration Protocol — Atlas Flow

Atlas Flow implements Project Atlas POP:

`Vision → Phase → Goal → Task DAG → isolated execution → verification → review → evidence → gate`

Rules: Goals remain repository canonical; planner cannot weaken acceptance; worktrees isolate mutable parallel tasks; retries bounded; high-risk review prefers provider diversity; deterministic checks outrank agent assertion; SQLite never replaces Git truth; model availability is runtime-probed; runner capabilities are negotiated.

For framework v0.2 projects, context follows the same bounded principle: start
with the smallest useful context, expand only when evidence is insufficient,
keep delegation depth bounded, and prefer pointers to duplicated payloads.
These rules describe the integration direction; the current C# runtime only
implements the manifest and Goal read boundary so that enabling the rest can be
validated independently.
