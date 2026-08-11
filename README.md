# Atlas Flow

**Atlas Flow** is the reference orchestration runtime for the Project Atlas Framework.

It turns durable project knowledge and locked Goals into observable, multi-agent execution while keeping Git—not chat history, an LLM provider, or the orchestrator database—as the canonical source of truth.

## Product thesis

```text
Idea
  ↓
Discuss
  ↓
Decisions + Project Draft
  ↓
Project Atlas documentation
  ↓
Goals
  ↓
Task DAG
  ↓
Agent/Skill resolution
  ↓
Model routing
  ↓
Isolated execution
  ↓
Verification + Evidence
  ↓
Review
  ↓
Release
```

## Key properties
- Project-type and stack agnostic.
- Project Atlas-native, but the framework remains independently usable.
- Goal-first rather than prompt-first.
- Agents are abstract roles; models and harnesses are replaceable.
- Git is durable memory; SQLite stores operational run state only.
- AG-UI for user-facing agent event streaming.
- ACP preferred for coding-agent interoperability.
- MCP for tools and external services.
- Command Code is the development harness for this project.
- DeepSeek V4 Pro and MiMo V2.5 Pro are the primary development models.
- GPT-5.6 Luna is the preferred efficient third model when present in the active Command Code registry.

## Entry points
- `ENTRYPOINT.md`
- `docs/ATLAS.md`
- `PROJECT_STATE.md`
- `.ai/goals/`
- `.ai/orchestration/`
- `.commandcode/`

## Running it

```sh
# Backend
uv run --project backend python -m uvicorn atlas_flow.api.app:create_app --factory

# Frontend, in another terminal
pnpm --filter @atlas-flow/desktop dev
```

Open http://localhost:1420. Atlas Flow opens any directory and first reports its
Project Atlas mode. An external project can be explored and discussed; after an
authorized adaptation, the workspace enables **Plan → Run → Review**. A Goal is
planned into a reviewable snapshot, locked, executed in isolated worktrees and
followed through evidence.

Run every check with `scripts/validate_all.sh`.

The first AF-EVO-001 foundation is available through the provider-agnostic
`atlas` CLI. It validates the v2 manifest and metadata, plans bounded context,
analyzes impact, records task cost and builds a visibility-filtered static docs
site:

```sh
uv run --project backend --all-groups atlas --root . validate --json
uv run --project backend --all-groups atlas --root . context "goal execution" --json
uv run --project backend --all-groups atlas --root . docs build --visibility internal
```

See [Atlas CLI](docs/06-user-guide/ATLAS_CLI.md) and the [v2 foundation](docs/03-implementation/ATLAS_FLOW_V2_FOUNDATION.md).

## Current state

Under active development. The Discuss → Goal → DAG → isolated execution →
evidence path runs end to end, on durable state, with a real ACP client and real
git worktrees.

Goal completion is enforced: `scripts/validate_goals.py` fails CI if a Goal
claims DONE without passing evidence for every required gate.

The largest open gap is that **no LLM is ever invoked** — the router picks model
identifiers, but the CLI and ACP runners are the only paths that perform work.

See `PROJECT_STATE.md` for per-Goal status and `VALIDATION_REPORT.md` for the
current check results and the full list of known gaps.
