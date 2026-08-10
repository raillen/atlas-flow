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

## Current state
Documentation complete. Implementation begins at **P00-G01 — Repository Foundation**.
