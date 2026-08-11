# Reliability and Fault Injection

Fail closed when canonical and operational state cannot be reconciled safely.

## Injected faults

`tests/integration/test_fault_injection.py` drives real runs through the whole
execution path with a runner that misbehaves in a specific way. A fault that
never reaches a run proves nothing about recovery, so none of these assert on a
bookkeeping class counting its own registrations.

| Fault | Expected behaviour |
| --- | --- |
| Provider timeout | Task FAILED, attempt FAILED with the error recorded, `build` gate evidence FAILED, run FAILED — never an exception out of `execute()` |
| Process kill mid-attempt | Same |
| Malformed runner output | Same |
| ACP disconnect | Same |
| Git conflict on integration | Task fails, nothing merged, outcome flagged `needs_human` — a conflict is a decision, not something to retry |
| Interrupted process (graceful cancel) | The attempt closes itself on unwind; recovery reconciles the orphaned task and blocks the run |
| Interrupted process (hard kill) | The attempt is still RUNNING on restart; recovery closes it FAILED along with its task |

Recovery is idempotent: running it twice finds nothing left to reconcile.
Operational state survives the process that wrote it — a new connection to the
same file sees the same runs, events and evidence.

## Not yet injected

SQLite contention under concurrent writers, cancellation during a write, rate
limiting from a provider, and stale Goal revisions.
