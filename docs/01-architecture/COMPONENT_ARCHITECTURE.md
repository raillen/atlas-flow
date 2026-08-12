# Component Architecture

## Backend

The current port is C#/.NET. Its implemented modules are `project`, `discuss`,
`goals`, `planner`, `context`, `intelligence`, `execution`, `events`,
`persistence`, `protocols` and `security`. Planned modules are tracked in
[Remaining Goals](../03-implementation/REMAINING_GOALS.md): documentation,
verification, runners, routing, settings, AG-UI and CLI.

## Frontend
`app-shell`, `discuss`, `plan`, `build`, `review`, `project`, `graph`, `chat`, `terminal`, `diff`, `settings`, `shared-ui`.

Keep domain logic out of UI projections and provider-specific adapters.
