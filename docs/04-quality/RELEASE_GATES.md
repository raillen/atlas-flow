# Release Gates

What must be true before Atlas Flow is released, and what is true today. This
table is the honest version: a gate is only PASS when something checkable says
so.

## Status on the C# port branch

Every gate below is **NOT ESTABLISHED** except documentation. That is not a
regression in the product — it is the correct reading of a branch where the
runtime changed and no behaviour has been ported.

The toolchain is verified and the first module is ported: restore, build with
warnings-as-errors, a NativeAOT publish that launches, and **29 passing tests**
over the ACP client, all on Linux as of 2026-08-11.

That is one module out of the runtime. It moves no gate on its own, and the
temptation to score a green build as partial credit is exactly what the rule at
the bottom of this page exists to refuse.

| Gate | Status | What it now requires |
| --- | --- | --- |
| Release Goals DONE with evidence | NOT ESTABLISHED | The validator is `scripts/validate_goals.py`, still Python. Its C# replacement has not been written, so no Goal on this branch can produce checkable evidence. |
| CI green on supported platforms | NOT ESTABLISHED | Two platforms now, not one. `foundation-ci.yml` targets a Python/Node/Rust toolchain that no longer exists and has to be rewritten for `dotnet` on `ubuntu-latest` and `windows-latest`. |
| Protocol contracts green | **PARTIAL** | ACP is ported and covered: 17 normalizer cases against the Python suite it came from, plus 12 against a fixture agent running as a real child process. MCP and AG-UI are not ported. There is no REST surface to cover any more. |
| No critical or high security findings | NOT ESTABLISHED | `dotnet list package --vulnerable --include-transitive` replaces pip-audit, pnpm audit and cargo audit. It must fail the build on any advisory and must treat an unreachable database as a failure, not a pass. |
| Performance within accepted variance | NOT ESTABLISHED | First figures exist and one already misses its estimate: 20 MB published binary against a 40 MB guess, but 114 MB RSS for an empty window against 80 MB. They are from a scaffold, not the product, and no budget in [Performance Budgets](PERFORMANCE_BUDGETS.md) has been re-derived for Avalonia. See also the note in [UX_FOUNDATION](../02-ui-ux/UX_FOUNDATION.md) about measurements that were pre-registered and then not taken. |
| Recovery suite | NOT ESTABLISHED | Both interrupt modes, idempotence and state that outlives its process must be re-covered in `AtlasFlow.Integration.Tests`. |
| Installation tests | NOT ESTABLISHED | `deb`, Flatpak and MSI. The full checklist is in [PACKAGING.md](../03-implementation/PACKAGING.md). |
| Project Atlas compatibility | NOT ESTABLISHED | Three project categories, built and executed end to end, on both platforms. |
| Updated documentation | **PASS** | The documentation was ported with the stack and states its own limits, including where the first measurements contradicted its own estimates. |
| SBOM, checksums and signature | NOT ESTABLISHED | One lockfile now (`packages.lock.json`) instead of three. The signing chain itself is unchanged and previously worked end to end. |
| Review | NOT ESTABLISHED | No review of the C# branch has been performed. The model-diversity rule applies again from scratch. |
| Accessibility | NOT ESTABLISHED | This gate previously leaned on the `axe-core` suite, which has no native equivalent. What replaces each part, and what nothing replaces, is in [ACCESSIBILITY.md](../02-ui-ux/ACCESSIBILITY.md). |

The previous stack passed most of these. Those results are preserved in
[`VALIDATION_REPORT.md`](../../VALIDATION_REPORT.md) as history and are
deliberately not carried across, because they described a Python backend and a
Tauri bundle that this branch deletes.

## Findings from the 2026-08-11 reviews

Historical, describing the superseded stack. Kept because the defects it records
are the ones a port is most likely to reintroduce.

Three rounds. The first two by a model other than the implementer: FAILED, then
PARTIAL. The third a self-review, authorised by the owner, which found two more
defects — a failing review verdict satisfying the review gate, and parallel
tasks overspending the attempt budget four to one. Both reproduced before being
fixed; see [the write-up](../07-decisions/reviews/2026-08-11-self-review.md).

| Finding | Status then | Carried into the port? |
| --- | --- | --- |
| Local gates could not be run at all | Closed | Re-check. The `noexec` workaround was Node/Cargo specific; `NUGET_PACKAGES` is the equivalent lever. |
| CI Linux-only | Closed | **Reopened.** CI must be rewritten for two platforms. |
| No `cargo build`/`test` in CI | Closed | Obsolete — no Rust. |
| No dependency audit | Closed | **Reopened** under a different tool. |
| Windows/macOS bundles unconfigured | Closed, then withdrawn | **Reopened for Windows** by ADR-018. macOS stays out of scope. |
| ACP does not resume a session | Closed | Must be re-covered by a test in the port; resumption with a stale-id fallback. |
| No DOM/screen-reader audit | Partly closed | **Reopened and cannot be closed the same way.** No `axe-core` for a native toolkit. |
| Artefacts unsigned | Closed | The GPG chain is unchanged and should survive; unverified here. |
| AppImage unverified | Closed | Obsolete — Flatpak replaces AppImage. |
| Dependency audit not reproducible locally | Closed | **Reopened** with the audit script. |
| `tests/e2e` held only a `.gitkeep` | Closed | Watch for it. An empty `AtlasFlow.Integration.Tests` is the same defect wearing a new name. |

## The rule this table exists to protect

A gate is not passed by writing that it is. `all_passed` exempts nothing:
a gate that is hard to satisfy has to be declared optional in the Goal, not
skipped at evaluation time. The same standard applies here — the NOT ESTABLISHED
rows stay that way until the artefact exists, and no row is rounded up because
the previous stack once passed it.
