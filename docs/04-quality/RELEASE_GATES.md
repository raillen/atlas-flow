# Release Gates

What must be true before Atlas Flow is released, and what is true today. This
table is the honest version: a gate is only PASS when something checkable says
so.

| Gate | Status | Evidence |
| --- | --- | --- |
| Release Goals DONE with evidence | **FAIL** | 0 of 11 Goals are DONE. `scripts/validate_goals.py` refuses a DONE Goal without passing evidence for every required gate. |
| CI green on supported platforms | **PARTIAL** | Ubuntu, macOS and Windows for Python, JavaScript and the desktop shell; plus dependency audit, validators and the packaging smoke test. macOS and Windows are newly added and have not yet reported. |
| Protocol contracts green | **PASS** | ACP against a live fixture agent, AG-UI envelopes, and the REST surface are covered by tests. |
| No critical or high security findings | **PASS** | Five findings closed, plus PYSEC-2026-1845 found by the new dependency audit; see [Security Testing](SECURITY_TESTING.md). |
| Performance within accepted variance | **PASS** | Measured and asserted in `tests/integration/test_performance.py`; see [Performance Budgets](PERFORMANCE_BUDGETS.md). |
| Recovery suite | **PASS** | `tests/integration/test_fault_injection.py` covers both interrupt modes, idempotence and state that outlives its process. |
| Installation tests | **PARTIAL** | `scripts/package_smoke.sh` verifies the `deb` bundle and runs in CI. Windows and macOS targets are configured but unbuilt; AppImage needs FUSE and a download the build machine did not have. |
| Project Atlas compatibility | **PASS** | Three project categories built and executed end to end; see [the compatibility matrix](../09-references/COMPATIBILITY_MATRIX.md). |
| Updated documentation | **PASS** | `scripts/validate_docs.py` checks every internal link; canonical docs are updated with each change. |
| SBOM and checksums | **PASS** (unsigned) | `scripts/package_smoke.sh` writes a CycloneDX 1.5 SBOM (791 components across pypi, npm and cargo) and `SHA256SUMS` beside the bundle. |
| Independent review | **FAIL** | Performed on 2026-08-11 by a different model, and it failed all eleven Goals. The findings it raised are addressed below; the gate stays FAIL until a re-review says otherwise. |

## Findings from the 2026-08-11 review

| Finding | Status |
| --- | --- |
| Local gates could not be run at all | Closed — `scripts/bootstrap.sh` + `scripts/run_gates.sh` |
| CI Linux-only | Closed — three-platform matrix |
| No `cargo build`/`test` in CI | Closed, and the shell has 9 unit tests instead of none |
| No dependency audit | Closed — found and fixed PYSEC-2026-1845 in pytest |
| Windows/macOS bundles unconfigured | Closed — targets and `.ico`/`.icns` icons |
| ACP does not resume a session | Closed — resumption with a stale-id fallback |
| No DOM/screen-reader audit | Partly — axe-core over every screen; no screen-reader walkthrough |
| `tests/e2e` held only a `.gitkeep` | Closed — the placeholder is gone, the audit is real |
| Artefacts unsigned | Open — needs a signing key and mechanism the owner chooses |
| AppImage unverified | Open — needs FUSE and network at build time |

## The rule this table exists to protect

A gate is not passed by writing that it is. `all_passed` exempts nothing:
a gate that is hard to satisfy has to be declared optional in the Goal, not
skipped at evaluation time. The same standard applies here — the FAIL rows stay
FAIL until the artefact exists, and the PARTIAL rows say what is missing rather
than rounding up.
