# Git and Worktrees

Mutable parallel tasks use dedicated worktrees/branches, suggested `atlas/{goal-id}/{task-id}`.

Never let parallel tasks silently mutate the same branch. Check declared scopes. Integrate after task gates. Conflicts are explicit. Never overwrite unrelated user changes.

Failed/cancelled worktrees remain until inspection/cleanup policy.
