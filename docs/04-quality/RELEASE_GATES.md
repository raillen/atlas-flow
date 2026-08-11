# Release Gates

What must be true before Atlas Flow is released, and what is true today. This
table is the honest version: a gate is only PASS when something checkable says
so.

| Gate | Status | Evidence |
| --- | --- | --- |
| Release Goals DONE with evidence | **FAIL** | 0 of 11 Goals are DONE. `scripts/validate_goals.py` refuses a DONE Goal without passing evidence for every required gate. |
| CI green on supported platforms | **PARTIAL** | Linux only. `foundation-ci.yml` runs lint, types, tests and the validators. |
| Protocol contracts green | **PASS** | ACP against a live fixture agent, AG-UI envelopes, and the REST surface are covered by tests. |
| No critical or high security findings | **PASS** | Five findings from this pass are closed; see [Security Testing](SECURITY_TESTING.md). No independent review has been performed. |
| Performance within accepted variance | **PASS** | Measured and asserted in `tests/integration/test_performance.py`; see [Performance Budgets](PERFORMANCE_BUDGETS.md). |
| Recovery suite | **PASS** | `tests/integration/test_fault_injection.py` covers both interrupt modes, idempotence and state that outlives its process. |
| Installation tests | **PARTIAL** | `scripts/package_smoke.sh` verifies the `deb` bundle. AppImage, Windows and macOS are unverified. |
| Project Atlas compatibility | **PASS** | Three project categories built and executed end to end; see [the compatibility matrix](../09-references/COMPATIBILITY_MATRIX.md). |
| Updated documentation | **PASS** | `scripts/validate_docs.py` checks every internal link; canonical docs are updated with each change. |
| SBOM and checksums | **FAIL** | Not produced. |
| Independent review | **FAIL** | Not performed. It is deliberately not self-certified — the `review` gate on every Goal stays open until someone other than the author signs it off. |

## The rule this table exists to protect

A gate is not passed by writing that it is. `all_passed` exempts nothing:
a gate that is hard to satisfy has to be declared optional in the Goal, not
skipped at evaluation time. The same standard applies here — the three FAIL rows
stay FAIL until the artefact exists.
