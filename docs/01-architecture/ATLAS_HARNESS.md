# Atlas Harness

Build a **meta-harness**, not a full coding agent.

Owns session lifecycle, runner selection, context, worktree, permissions, transcript, cancellation, usage, fallback, recovery and evidence linkage.

Coding agents own their internal reasoning/tool loop.

Runner preference:
1. ACP.
2. Native SDK where uniquely useful.
3. Generic CLI.
4. Direct API for narrow non-coding tasks.

Harness never treats a coding-agent transcript as canonical project truth.
