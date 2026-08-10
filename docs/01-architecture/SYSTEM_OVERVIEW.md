# System Overview

```text
                     USER
                      │
                Atlas Flow UI
                      │
                    AG-UI
                      │
             ┌────────┴────────┐
             │ Atlas Flow Core │
             └────────┬────────┘
                      │
        ┌─────────────┼────────────────┐
        │             │                │
 Project Atlas    Orchestration    Operational DB
 Framework            │              SQLite
        │              │
  Git canonical      Atlas Harness
  project truth        │
                       │ ACP / CLI / SDK
          ┌────────────┼──────────────┐
          │            │              │
      Command Code   Codex/etc.   Generic agents
          │
          └──────────────→ LLM providers

MCP connects agents/runtime to external tools and services.
```

## Boundaries
- Git owns canonical project knowledge.
- Project Atlas owns protocol semantics.
- Atlas Flow owns orchestration semantics and operational run state.
- Runner owns mechanics of interacting with coding agents.
- Models provide intelligence but no project authority.
- UI projects backend state and mutates through commands.
