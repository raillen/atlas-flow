# Release Gates

What must be true before Atlas Flow is released, and what is true today. This
table is the honest version: a gate is only PASS when something checkable says
so.

| Gate | Status | Evidence |
| --- | --- | --- |
| Release Goals DONE with evidence | **PASS** | 11 of 11. Each carries evidence for build, tests, review and documentation, and `scripts/validate_goals.py` refuses a DONE Goal without it — including, since 2026-08-11, evidence that opens with a failing verdict. |
| CI green on supported platforms | **PARTIAL** | The supported platform is Linux. `foundation-ci.yml` runs Python, JavaScript, the desktop shell, the dependency audit, the validators and the packaging smoke test on ubuntu-latest. No hosted result has been observed yet — it reports on the next push. |
| Protocol contracts green | **PASS** | ACP against a live fixture agent, AG-UI envelopes, and the REST surface are covered by tests. |
| No critical or high security findings | **PASS** | `sh scripts/audit_dependencies.sh` runs pip-audit, pnpm audit and cargo audit locally and in CI, and reports being unable to reach a database as a failure rather than a pass. No independent security review has been performed. See [Security Testing](SECURITY_TESTING.md). |
| Performance within accepted variance | **PASS** | Measured and asserted in `tests/integration/test_performance.py`; see [Performance Budgets](PERFORMANCE_BUDGETS.md). |
| Recovery suite | **PASS** | `tests/integration/test_fault_injection.py` covers both interrupt modes, idempotence and state that outlives its process. |
| Installation tests | **PASS** | `sh scripts/package_smoke.sh` builds and verifies both supported bundles — `.deb` and AppImage, the latter unpacked and checked for its executable — plus SBOM, checksums and signature. |
| Project Atlas compatibility | **PASS** | Three project categories built and executed end to end; see [the compatibility matrix](../09-references/COMPATIBILITY_MATRIX.md). |
| Updated documentation | **PASS** | `scripts/validate_docs.py` checks every internal link; canonical docs are updated with each change. |
| SBOM, checksums and signature | **PASS** | `scripts/package_smoke.sh` writes a CycloneDX 1.5 SBOM (840 components), `SHA256SUMS` over the `.deb`, AppImage and SBOM, and a detached GPG signature. The project key exists (`C4ECF972E0FFC81D`), its public half is committed, and the whole chain — import, verify, `sha256sum -c` — was exercised from a clean keyring. |
| Review | **PASS** (self-review) | Two rounds by a different model (FAILED, then PARTIAL) with every finding closed, then a self-review after the owner waived model diversity and undertook a second reading of their own. Recorded as a self-review everywhere it appears: [the write-up](../07-decisions/reviews/2026-08-11-self-review.md) states its own limitations and the two defects it found. |

One row is still PARTIAL and says why: no hosted CI result has been observed
yet, because that needs a push. Everything else is checkable now and was
checked.

## Findings from the 2026-08-11 reviews

Three rounds. The first two by a model other than the implementer: FAILED, then
PARTIAL. The third a self-review, authorised by the owner, which found two more
defects — a failing review verdict satisfying the review gate, and parallel
tasks overspending the attempt budget four to one. Both reproduced before being
fixed; see [the write-up](../07-decisions/reviews/2026-08-11-self-review.md).

| Finding | Status |
| --- | --- |
| Local gates could not be run at all | Closed — bootstrap relocates Python/Cargo environments; Node tools and Tauri frontend build now use JS entrypoints where the checkout is noexec. |
| CI Linux-only | Closed — three-platform matrix |
| No `cargo build`/`test` in CI | Closed, and the shell has 9 unit tests instead of none |
| No dependency audit | Closed — found and fixed PYSEC-2026-1845 in pytest |
| Windows/macOS bundles unconfigured | Closed — targets and `.ico`/`.icns` icons |
| ACP does not resume a session | Closed — resumption with a stale-id fallback |
| No DOM/screen-reader audit | Partly closed — axe-core/DOM suite passes 11 tests; the manual screen-reader walkthrough is deferred by owner decision |
| Artefacts unsigned | Closed — project key created, releases signed, verification exercised from a clean keyring |
| AppImage unverified | Closed — `APPIMAGE_EXTRACT_AND_RUN=1` removes the FUSE requirement; built, unpacked, checked |
| Dependency audit not reproducible locally | Closed — `scripts/audit_dependencies.sh`, used by CI and by `run_gates.sh` |
| No hosted result for Windows/macOS | Withdrawn — macOS and Windows are out of scope by owner decision (2026-08-11) |
| `tests/e2e` held only a `.gitkeep` | Closed — the placeholder is gone, the audit is real |

## The rule this table exists to protect

A gate is not passed by writing that it is. `all_passed` exempts nothing:
a gate that is hard to satisfy has to be declared optional in the Goal, not
skipped at evaluation time. The same standard applies here — the FAIL rows stay
FAIL until the artefact exists, and the PARTIAL rows say what is missing rather
than rounding up.
