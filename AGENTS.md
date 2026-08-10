# Atlas Flow Agent Guide

## Project
Atlas Flow is the provider-agnostic orchestration runtime for Project Atlas Framework.

## First reads
- `@ENTRYPOINT.md`
- `@PROJECT_STATE.md`
- `@docs/ATLAS.md`
- active Goal in `@.ai/goals/`

## Mandatory rules
- Git is canonical durable memory.
- Do not bypass Goal gates or reduce locked acceptance criteria.
- Keep Project Atlas Framework and Atlas Flow separable.
- Agents are roles; never embed provider/model names in canonical agent definitions.
- Prefer open protocols: AG-UI for UI/runtime, ACP for coding agents, MCP for tools.
- Atlas Harness coordinates existing coding agents; it does not rebuild a full coding agent loop by default.
- Use worktrees/isolated branches for independent mutable tasks.
- Store operational state in SQLite; canonical product/architecture/Goal decisions remain in Git.
- High-risk implementation should receive cross-provider review when the roster permits.
- Keep retries bounded and escalate rather than loop indefinitely.

## Development harness
Command Code.

## Model policy
See `.ai/orchestration/model-policy.yaml`.

## Completion
Before proposing Goal completion:
- build/typecheck/lint;
- relevant tests;
- architecture/Goal conformance review;
- required evidence;
- documentation updates.
