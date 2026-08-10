# Getting Started

## Prerequisites
- Python 3.12+ with `uv` (or pip)
- Node.js 24+ with `pnpm` 11+
- Rust (for Tauri desktop builds)
- Command Code CLI (`cmd`) for development

## Install

```bash
git clone <repo-url> atlas-flow
cd atlas-flow

# Backend
cd backend && uv sync

# Frontend
pnpm install
```

## Start Development

```bash
# Terminal 1: Backend
cd backend && uv run uvicorn atlas_flow.api.app:create_app --factory --reload

# Terminal 2: Frontend
pnpm --filter @atlas-flow/desktop dev
```

Open **http://localhost:1420** for the 5-mode desktop shell:
- **Discuss** — chat with AG-UI WebSocket, propose decisions
- **Plan** — view DAG tasks, dependencies, status
- **Build** — live task status with runner/model info
- **Review** — gate results (build/tests/review/documentation), evidence
- **Project** — canonical docs browser, phases, agents/skills overview

## Run Validation Gates

```bash
# Python
uv run --project backend ruff check .
uv run --project backend mypy
uv run --project backend pytest tests/unit/

# Frontend
pnpm run typecheck
pnpm run lint
pnpm run test

# Project Atlas
uv run --project backend python scripts/validate_docs.py
uv run --project backend python scripts/validate_goals.py
```

## Architecture
See `docs/ATLAS.md` for the full documentation map.
Backend: `atlas_flow/` (FastAPI + SQLite operational store).
Frontend: `apps/desktop/` (Tauri 2 + React + TypeScript).
Protocols: AG-UI for UI↔backend, ACP for harness↔coding agents, MCP for tools.
Project Atlas Framework is consumed as a protocol dependency, never vendored.
