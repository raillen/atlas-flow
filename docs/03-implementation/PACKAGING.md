# Packaging and Distribution

The desktop client is a single NativeAOT executable built from
`src/AtlasFlow.Desktop`. There is no sidecar, no interpreter and no runtime for
the user to install.

**Development platform: Linux x86_64.** Avalonia keeps Windows reachable and
ADR-018 chose it partly for that, but Windows work is deferred by owner
decision and Linux is what gets built and tested. macOS remains out of scope.

Nothing here claims a platform it does not build and test. Linux builds,
publishes and launches; Windows has not been attempted. See
[Verified](#verified).

## What the shell used to own, and no longer does

The Tauri build exposed four IPC commands so that a webview could reach an
orchestrator running in another process:

| Command | Why it existed |
| --- | --- |
| `backend_status` | Whether a spawned backend was still alive |
| `start_backend` | Start it, idempotently |
| `stop_backend` | Kill the one this window started |
| `project_root` | Find the nearest `PROJECT_MANIFEST.yaml` |

Three of those four are deleted rather than ported. `AtlasFlow.Desktop`
references `AtlasFlow.Application` and calls it directly, so there is no process
to start, no port to race for, no exit status to interpret and no state to
render for a backend that failed to come up. `project_root` survives as an
ordinary method.

This is the largest single simplification in the port, and it is the reason the
port was worth doing rather than merely worth wanting.

Overrides that remain: `ATLAS_FLOW_PROJECT_ROOT` sets the working project when
the app is launched from outside one.

## Building

```sh
dotnet publish src/AtlasFlow.Desktop -c Release -r linux-x64
dotnet publish src/AtlasFlow.Desktop -c Release -r win-x64
```

`PublishAot`, `SelfContained` and `StripSymbols` are set for Release in the
`.csproj`, so those flags do not need to be passed and cannot be forgotten.

**Always verify a change against a Release publish, not `dotnet run`.**
NativeAOT rejects runtime code generation and unbounded reflection. A dependency
or a serializer that works in Debug and fails at AOT publish — or worse, fails
at startup in the shipped artefact — is the most common way a green local build
produces a broken release.

Targets: `deb` and Flatpak on Linux, MSI on Windows. Flatpak is preferred over
AppImage now that the binary is self-contained: there is no advantage left in
the extract-and-run machinery.

## Signing and verifying

Unchanged by the port. The release key is
`Atlas Flow Release Signing <raillen@atlas-flow.dev>`, fingerprint
`1AAF FA26 944C 1D56 B850  AAE8 C4EC F972 E0FF C81D`, expiring 2028-08-10. Its
**public half** is committed at
[`docs/09-references/RELEASE_SIGNING_KEY.asc`](../09-references/RELEASE_SIGNING_KEY.asc);
the private half lives only in the maintainer's keyring and is never in this
repository — `.gitignore` refuses the shapes a private key comes in.

To sign a build:

```sh
ATLAS_SIGNING_KEY=C4ECF972E0FFC81D sh scripts/package_smoke.sh
```

To verify one, as anybody downloading it would:

```sh
gpg --import docs/09-references/RELEASE_SIGNING_KEY.asc
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum -c SHA256SUMS
```

The signature covers the digest list rather than each artefact: that is what a
verifier checks, and it cannot be sidestepped by swapping a file the list
already names.

The key carries **no passphrase**, so scripts and CI can use it unattended. That
is a deliberate trade: anyone who can read the maintainer's home directory can
sign as the project. Add one with `gpg --change-passphrase C4ECF972E0FFC81D`
and give CI a separate exported key if that trade stops being acceptable.

Renewal, before 2028-08-10:
`gpg --quick-set-expire 1AAFFA26944C1D56B850AAE8C4ECF972E0FFC81D 2y`

## Release artefacts

Written beside the package, so a build and the record of what is inside it never
drift apart:

- `sbom.cyclonedx.json` — CycloneDX 1.5. Generated from `packages.lock.json`
  rather than from an installed environment, so the SBOM describes the release
  and not the machine that built it. One lockfile now, where the Tauri build
  needed three (`uv.lock`, `pnpm-lock.yaml`, `Cargo.lock`).
- `SHA256SUMS` — over each package and the SBOM.
- `SHA256SUMS.asc` — a detached GPG signature when `ATLAS_SIGNING_KEY` names a
  key. The script verifies its own signature before reporting success. With no
  key configured it prints `unsigned` and carries on — an unsigned release that
  claims to be signed is worse than one that admits it.

## Verified

Measured on 2026-08-11: Arch Linux, x86_64, .NET SDK 10.0.110.

| Step | Result |
| --- | --- |
| `dotnet restore` | 13 projects, clean — after pinning two transitive advisories |
| `dotnet build` | 0 warnings, 0 errors, with warnings-as-errors and `AnalysisMode=All` |
| `dotnet test` | Hosts start in all 6 test projects. **0 tests exist.** |
| AOT publish, `linux-x64` | Succeeds for both `AtlasFlow.Cli` and `AtlasFlow.Desktop` |
| `atlas` binary | **2.9 MB**, runs, prints help |
| `atlas-flow` binary | **20 MB** (the 86 MB publish directory is debug symbols, which do not ship) |
| Desktop launch | Opens a window titled "Atlas Flow" and stays up. RSS **114 MB** |

The first restore failed with eleven `NU1903` errors — high-severity advisories
in `SQLitePCLRaw.lib.e_sqlite3` and `Tmds.DBus.Protocol`, both transitive. That
is the dependency policy working rather than failing: an advisory is an error,
so the build stopped. Both are pinned forward in `Directory.Packages.props`,
each pin annotated with its advisory and the condition for removing it.

Read the RSS number carefully. It is an **empty window** — a `TextBlock` in a
`Window`, with no orchestrator attached. It is not a measurement of the product,
and it is above the 80 MB this document previously estimated. The comparison it
does support: the previous stack needed roughly 250 MB and a Python interpreter
present on the machine.

## Not verified

- **Windows. Nothing at all.** No build, no publish, no launch, no MSI — and none is scheduled while development is Linux-first.
- **`deb`, Flatpak and MSI packaging.** No package has been produced.
- **SBOM, checksums and signature** against a .NET artefact.
- **Any behaviour.** Zero tests exist. The binary opens a window that does
  nothing, which is what a scaffold is.

## Not yet done

- **Everything under [Not verified](#not-verified).**
- **A published signing key.** The mechanism works; no project key exists or is
  distributed, so released artefacts are still effectively unsigned.
- **A LICENSE file.** The repository has no license text, so no package can
  carry one.
- **Icons.** `scripts/generate_icons.py` is Python and targeted the Tauri
  bundler's layout. Windows needs an ICO, which that script could produce behind
  `--all-platforms` but never shipped.
