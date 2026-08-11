# Plan UX

Views: Phase list, Goal board, DAG, Workforce, Context preview.

Goal panel shows objective, constraints, non-goals, acceptance, dependencies, gates, evidence.

DAG nodes communicate role, state, risk, write scope, route and gate. Cycles block execution.

Controlled/Agentic modes expose explicit Lock & Run.

## The graph and its alternative

The plan is drawn as an SVG: one column per dependency layer, left to right in
the order the scheduler will run them, with curved edges between tasks that
actually depend on each other. An edge pointing at a task that is not on screen
is dropped rather than drawn into space.

Beneath it is the same information as a list of stages. That list is a **peer,
not a fallback**: a drawing alone is unreadable to a screen reader, so the
graph carries `role="img"` with a sentence describing its shape, and the stage
list carries the detail. Neither is the lesser version of the other.

Nothing clever is attempted about crossing edges. A plan wide enough for that
to matter is a plan whose stage list is the better view anyway.
