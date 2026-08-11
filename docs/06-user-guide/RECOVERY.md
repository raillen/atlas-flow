# Recovery

## After a crash

Operational state is written transactionally: every state change lands with the
event that explains it, so what recovery reads back can never disagree with the
log. Reopening the project is enough — runs, tasks, attempts, events and
evidence are all still there.

What a crash leaves behind is work that *looks* active with no process behind
it. Recovery closes it:

- an attempt still `RUNNING` is failed, with the reason recorded as
  "interrupted by process restart";
- its task is failed too, and a failed task is retryable;
- a run whose tasks were reconciled moves to `BLOCKED`, so nobody mistakes it
  for still progressing.

Running recovery twice finds nothing left to do. It is safe to run whenever you
are unsure.

Task worktrees are deliberately left in place. A failed or cancelled task's
worktree survives so you can inspect what it did before deciding to discard it.

## After losing chat or model context

Atlas Flow reloads `PROJECT_MANIFEST.yaml`, `PROJECT_STATE.md`, `docs/ATLAS.md`,
the active Goal and the local operational state. Nothing important lives only in
a conversation.

If Atlas Flow itself is unavailable, any Project Atlas–capable agent can pick up
the project from `ENTRYPOINT.md`: canonical truth is in Git, and `.atlas-flow/`
holds only run history.

## Deleting operational state

`rm -rf <project>/.atlas-flow` is safe. You lose run history and in-flight runs;
you lose nothing that Git was the authority for.
