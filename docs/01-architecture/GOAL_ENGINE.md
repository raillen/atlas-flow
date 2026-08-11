# Goal Engine

Consumes Project Atlas Goals; no second Goal format.

State machine:
`DRAFT → PLANNED → LOCKED → EXECUTING → VERIFYING → REVIEWING → DONE`, with policy-defined `BLOCKED`.

Responsibilities: schema validation, legal transitions, lock protection, dependencies, amendment, evidence completeness and closure.

Locked Goals change only through explicit amendment. Test failure never justifies weaker acceptance.

## Closing a Goal without a human

A Goal declares which gates it requires. Until 2026-08-11 only `build` ever got
evidence during a run — as a side effect of a runner succeeding — so a Goal that
Atlas Flow planned and executed could never become completable on its own.
Planning and execution worked; verification did not close.

The runtime cannot guess how a project runs its tests, and guessing wrong is
worse than not knowing: a command that fails for the wrong reason is recorded as
failing evidence. So the project declares them in
`.ai/orchestration/verification.yaml`:

```yaml
gates:
  tests: "python -m pytest tests/unit -q"
  documentation: "python scripts/validate_docs.py"
```

They run once, after every task in the run has succeeded — verifying
half-finished work reports on something nobody asked about — from the project
root, as argv rather than through a shell. Output is redacted and truncated
before it becomes the evidence's `uri`, so a verdict can be traced to the
command that produced it.

A gate with no declared command records nothing and stays PENDING. "Nobody
checked" has to stay distinguishable from "checked and failed".

This project's own file deliberately does not point at `scripts/run_gates.sh`:
Atlas Flow running a Goal in its own repository would then run the suite that
runs Atlas Flow. A verification command must not contain the thing being
verified.
