# Review — 2026-08-11 (self-review, implementer)

**Reviewer:** the model that implemented the work (Opus 5).
**Authorised by:** the project owner, on 2026-08-11, waiving the
model-diversity requirement recorded in `.commandcode/taste/taste.md`.
**Second reader:** the owner, who stated they would review independently.

## What kind of assurance this is

Read this record knowing what produced it. Two earlier reviews on the same day
were performed by a different model; both found things this author had missed,
including that the local gates could not be run at all — invisible from here
because they ran on this machine. Twice in the same session this author called
something "verified" when it was not: an eslint run that never executed, and an
AppImage that only built with environment variables supplied by hand.

The blind spot is structural: an implementer cannot find a defect whose cause is
an assumption they still hold. This pass was conducted with that in mind —
every claim below was checked by running something, and the two defects found
were reproduced before being fixed.

## Findings

### 1. A failing review satisfied the review gate — **fixed**

`check_declared_evidence` counted any truthy evidence value as covering its
gate. A Goal carrying

```yaml
evidence:
  - review: "FAILED — the reviewer rejected this Goal"
```

was reported **completable**. The gate whose entire purpose is independent
refusal could be satisfied by recording the refusal.

This was live, not hypothetical: all eleven Goals currently carry
`review: "PARTIAL — ..."`, so `scripts/validate_goals.py` would have accepted
DONE on every one of them.

Reproduced, then fixed: an entry opening with `FAILED`, `PENDING`, `PARTIAL`,
`BLOCKED`, `UNVERIFIED` or `SKIPPED` now marks the gate as *failing*, not as
covered, and the checker says which. Five parametrised regression tests, plus
one that a word merely beginning like a verdict ("Failedover to the backup
reviewer; approved") still passes.

### 2. Parallel tasks overspent the attempt budget — **fixed**

`_attempt_with_fallback` called `check_can_start_attempt()` before the model
invocation and `record()` after it. An attempt is a long `await`, and tasks run
concurrently, so every parallel task passed the same check before any had
counted itself.

Reproduced: a ledger capped at **one** attempt bought **four**.

```
['task0: rodou', 'task1: rodou', 'task2: rodou', 'task3: rodou']
teto: 1 | gastos: 4
```

Fixed by splitting reservation from accounting: `reserve_attempt()` checks and
claims in one synchronous step before the await; `record()` only accumulates
tokens and cost. A crash between the two no longer frees the slot, which is the
safe direction to fail. Three regression tests, including the four-way race.

### 3. Reads during a multi-statement transaction — **checked, not reproduced**

`Persistence.query` does not take the write lock, so in principle a read could
land between the two statements of `record_task_transition` and observe a state
change without the event that explains it — contradicting the invariant the
persistence documentation states.

A 60-iteration probe racing readers against transitions observed **0** torn
reads. Not reproduced, so **nothing was changed**. Changing code to fix a
failure nobody has seen adds risk in exchange for a guess. Recorded here so the
next reader knows the question was asked and how it was answered.

## What was verified rather than assumed

| Claim | How it was checked |
| --- | --- |
| Every gate passes | `sh scripts/run_gates.sh` — 12 gates, all PASS |
| 328 Python, 57 TypeScript, 9 Rust tests | run, not counted from memory |
| The gate runner reports which gate failed and exits non-zero | forced two failures in a stand-in script |
| Releases are signed and verifiable | imported the committed public key into an empty keyring, `gpg --verify`, `sha256sum -c` |
| The packaged app works | AppImage launched on a real desktop; ran P00-G01 to 5 succeeded tasks; 53 models discovered through Command Code |
| Dependencies carry no known vulnerabilities | `sh scripts/audit_dependencies.sh` |

## Verdict

**PASS**, with the two defects above found and fixed during the review, and the
limitation at the top of this document attached to it. The gate is recorded as a
self-review, not as an independent one, so nobody later mistakes it for
something it is not.
