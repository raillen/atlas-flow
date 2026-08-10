# API Contracts

Version local backend under `/api/v1`.

Domains: Projects, Discuss, Goals, Runs, Settings.

Projects: open/close, state, validate, recover.
Discuss: discussions, turns, decisions, draft, readiness, finalize.
Goals: list/get/validate/amend/transition.
Runs: create/pause/resume/cancel, graph, events, evidence, route explanation.
Settings: runners, models, budgets, permissions, MCP.

Streaming uses AG-UI instead of bespoke websocket shapes.
