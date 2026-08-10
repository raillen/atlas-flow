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
uv run --project backend uvicorn atlas_flow.api.app:create_app --factory

# Frontend, in another terminal
pnpm --filter @atlas-flow/desktop dev
```

Open http://localhost:1420. The **Plan** tab lists the Goals declared in Git;
starting one decomposes it into a task per acceptance criterion, runs each in its
own git worktree, and switches to **Build**, which follows the run live.

Run every check with `scripts/validate_all.sh`.

## Current state

Under active development. The Discuss → Goal → DAG → isolated execution →
evidence path runs end to end, on durable state, with a real ACP client and real
git worktrees.

**No Goal is DONE**, and that is enforced: `scripts/validate_goals.py` fails CI if
a Goal claims DONE without passing evidence for every gate it declares required.

The largest open gap is that **no LLM is ever invoked** — the router picks model
identifiers, but the CLI and ACP runners are the only paths that perform work.

See `PROJECT_STATE.md` for per-Goal status and `VALIDATION_REPORT.md` for the
current check results and the full list of known gaps.
