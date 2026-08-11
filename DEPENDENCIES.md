# Dependency Policy

Atlas Flow follows Project Atlas ADR-001: the framework and runtime are separate
products. This dependency policy keeps both separable.

## Principles

- **One version per package, declared once.** `Directory.Packages.props` is
  canonical and Central Package Management is enabled, so a `.csproj` cannot
  carry a version of its own. Two projects on two versions of the same package
  is a class of bug this makes unrepresentable rather than merely discouraged.
- **Lockfile tracked in Git.** `packages.lock.json` is committed and CI restores
  with `--locked-mode`, so a restore that would silently resolve a different
  version fails instead.
- **Pinned versions, ranges reviewed.** Exact versions in
  `Directory.Packages.props`; transitive pinning is on.
- **Renovate keeps things current.** Weekly grouped updates. Automerge only for
  test-only package patch bumps when CI is green.
- **Framework vs runtime separation.** Project Atlas Framework packages are
  consumed as protocol dependencies, never vendored. Atlas Flow owns its own
  implementation and dependencies.
- **Provider independence.** No LLM provider SDKs in any project. Model routing
  is runtime-discovered via Command Code / ACP.
- **MCP only where required.** MCP client/server dependencies are added by
  protocol engineering Goals, not the foundation.
- **Security audits.** Lockfile changes trigger an SBOM diff and a license check
  in CI. `dotnet list package --vulnerable --include-transitive` fails the build
  on any advisory.

## Deliberately few

The dependency list is short because the workload is process supervision, JSON,
SQLite and Git — not a domain with heavy libraries. `System.Text.Json`,
`System.Diagnostics.Process` and `System.Threading.Channels` are in the base
class library, so most of the runtime carries no third-party code at all.

The exceptions, and why each earns its place:

| Package | Why not the BCL |
| --- | --- |
| `Avalonia` | Cross-platform UI with a real accessibility surface (UIA, AT-SPI). |
| `CommunityToolkit.Mvvm` | Source-generated observables; the alternative is hand-written boilerplate in every view model. |
| `Microsoft.Data.Sqlite` | The ADO.NET provider. Thin over the native library. |
| `YamlDotNet` | `PROJECT_MANIFEST.yaml` and the Goal files are YAML. There is no YAML reader in the BCL. |
| `System.CommandLine` | Argument parsing, help and completion for `atlas`. |

## Adding a dependency

1. Justify in the Goal/ADR that introduces it.
2. Prefer well-maintained packages with compatible licenses (MIT, Apache 2.0).
3. Add the version to `Directory.Packages.props` — never to a `.csproj`.
4. Run `dotnet restore` and commit the updated `packages.lock.json`.
5. Verify CI passes before merging.

## NativeAOT constraint

Release builds publish with NativeAOT. A package that requires runtime code
generation or unbounded reflection will either fail to publish or fail at
startup in a way that a Debug build never reproduces.

Any new dependency must be checked against a Release publish, not only against
`dotnet run`. This is the single most common way a change passes locally and
breaks the shipped artefact.
