# Git and Worktrees

Mutable parallel tasks use dedicated worktrees and branches, named
`atlas/{goal-id}/{task-id}`, checked out under `.atlas-flow/worktrees/`.

Never let parallel tasks silently mutate the same branch. Check declared scopes.
Integrate after task gates. Conflicts are explicit. Never overwrite unrelated
user changes.

## Scheduling

Two tasks may run in parallel only when neither depends on the other *and* their
declared write scopes cannot overlap — a scope that contains another is treated
as overlapping. Tasks that would collide are placed in separate batches and run
in sequence.

## Integration

Work is committed in its own worktree, then merged into the target branch.
Integration is refused, never forced, in two cases:

- **The target checkout has uncommitted changes.** Merging over them risks
  destroying work Atlas Flow did not create.
- **The merge would conflict.** Conflicts are detected with
  `git merge-tree --write-tree`, which performs the merge in the object database
  only, so a conflicting task never leaves the target half-merged for a human to
  clean up.

Both cases need a decision, and the run reports which paths conflicted rather
than choosing a side.

Integration into a shared branch is serialized. Tasks work in parallel, but two
concurrent merges race on `HEAD` and one dies with `cannot lock ref`.

## Cleanup

Failed and cancelled worktrees remain until inspection. Removing a worktree with
uncommitted changes requires an explicit force.
