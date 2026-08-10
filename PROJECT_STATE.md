# Current Project State

**Project:** Atlas Flow  
**Framework:** Project Atlas Framework 0.1.0  
**Status:** MVP ready — P00-P05 DONE  
**Current phase:** P05 — Planner & DAG execution (MVP complete)

## Approved direction
- Atlas Flow is generic; no Brasa Engine-specific behavior.
- Project Atlas Framework is the source of protocol, registries, Goals and project knowledge.
- Atlas Flow is the reference execution/orchestration runtime.
- Chat/Discuss is a first-class mode that can turn conversation into Project Atlas documentation.
- Canonical project truth stays in Git.
- Operational execution state uses SQLite plus append-only events.
- Frontend: Tauri 2 + React + TypeScript.
- UI building blocks: shadcn/ui + React Flow; CopilotKit may be used selectively.
- Frontend/runtime agent events: AG-UI.
- Coding-agent client protocol: ACP preferred.
- Tool integration: MCP.
- Backend/orchestration core: Python, reusing Project Atlas.
- Atlas Harness is a meta-harness coordinating existing coding agents.
- Command Code is the development harness.
- Primary models: DeepSeek V4 Pro and MiMo V2.5 Pro.
- GPT-5.6 Luna is used for efficient/high-volume roles when available in Command Code.

## Next action
Review MVP; launch backend (uvicorn atlas_flow.api.app:create_app) and test Discuss UI at localhost:1420.
