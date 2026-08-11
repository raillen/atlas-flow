# Packaging and Distribution

The desktop client is a single NativeAOT executable built from
`src/AtlasFlow.Desktop`. There is no sidecar, no interpreter and no runtime for
the user to install.

**Supported platforms: Linux x86_64 and Windows x86_64.** Windows was a recorded
non-goal on P06, P09 and P10 under an owner decision of 2026-08-11; ADR-018
reopens it, and those three Goals inherit the work. macOS remains out of scope.

Nothing here claims a platform it does not build and test. At the time of
writing that is **every platform** — see [Verified](#verified).

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

**Nothing.** No .NET SDK was available on the machine this branch was written
on. The solution has not been restored, compiled, published or packaged, and the
package versions in `Directory.Packages.props` are unconfirmed guesses.

The previous stack's verification results are deliberately not carried over.
They were true statements about a Tauri bundle that this branch deletes, and
reproducing them here under new headings would be a false claim about software
that has never been built.

To be established before any release claim:

- [ ] `dotnet restore` resolves every package
- [ ] `dotnet build` clean, with warnings as errors
- [ ] `dotnet test` green
- [ ] Release AOT publish succeeds on `linux-x64`
- [ ] Release AOT publish succeeds on `win-x64`
- [ ] The published binary starts and opens a window on both platforms
- [ ] `deb` contains the executable, desktop entry and icons
- [ ] Flatpak manifest builds
- [ ] MSI installs and uninstalls cleanly
- [ ] SBOM generated from `packages.lock.json`
- [ ] Signing exercised end to end

## Not yet done

- **Everything in the checklist above.**
- **A published signing key.** The mechanism works; no project key exists or is
  distributed, so released artefacts are still effectively unsigned.
- **A LICENSE file.** The repository has no license text, so no package can
  carry one.
- **Icons.** `scripts/generate_icons.py` is Python and targeted the Tauri
  bundler's layout. Windows needs an ICO, which that script could produce behind
  `--all-platforms` but never shipped.
