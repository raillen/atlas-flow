# Atlas Flow Entry Point

When working on Atlas Flow:

1. Read `atlas.json` when present; otherwise read `PROJECT_STATE.md` first.
2. Read `PROJECT_STATE.md` and `docs/ATLAS.md`.
3. Read the active Goal under `.ai/goals/`.
4. Read only the canonical documents linked from that Goal and ATLAS.
5. Read accepted ADRs relevant to the affected subsystem.
6. Follow `docs/05-governance/PROJECT_ORCHESTRATION_PROTOCOL.md`.
7. Follow the selected JSON orchestration policy when present; otherwise use
   the current YAML policy files.
8. Use selected Project Atlas Skills instead of loading every skill.
9. Never silently weaken locked acceptance criteria.
10. Evidence—not an agent's assertion—determines completion.

## Authority order
1. Explicit current user/project decision.
2. Accepted project ADR/RFC and locked Goal.
3. Canonical Atlas Flow documentation.
4. Project manifests/configuration.
5. Project Atlas Framework.
6. Command Code/platform adapter.
7. Model defaults.

## Command Code
Read `AGENTS.md` and `.commandcode/AGENTS.md`.
