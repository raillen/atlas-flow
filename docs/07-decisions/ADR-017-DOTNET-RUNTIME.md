# ADR-017 — One .NET runtime, not three

**Status:** Accepted · 2026-08-11
**Supersedes:** [ADR-003](ADR-003-PYTHON-BACKEND.md)
**Related:** [ADR-018](ADR-018-AVALONIA-DESKTOP.md)

## Context

Atlas Flow shipped as three runtimes:

| Layer | Size | Runtime |
| --- | --- | --- |
| `backend/atlas_flow` | 10,051 lines | CPython 3.12 + `uv` |
| `apps/desktop/src` | 6,266 lines | Node to build, webview to run |
| `apps/desktop/src-tauri` | 751 lines | Rust |

The 751 lines of Rust were mostly a state machine for starting the Python
backend: spawn `uv run … uvicorn`, strip the AppImage's `PYTHONHOME` and
`LD_LIBRARY_PATH` out of the child environment, poll `localhost:8000`, decide
whether a process that exited immediately counts as started, report a log path
when it did not.

None of that is product. All of it is the cost of the boundary.

And the boundary could not be paid off. `PACKAGING.md` recorded, as the main
open question for 1.0: *the packaged app expects a backend it can start from the
project directory; it does not carry its own interpreter.* A user without Python
and `uv` could not run a downloaded build.

The workload itself is not Python-shaped. It is: supervise long-lived child
processes over stdio JSON-RPC, run `git`, schedule a DAG with concurrency and
budget limits, persist to SQLite, stream events to a UI, parse YAML. No numeric
computing, no LLM SDK. The backend's whole third-party surface was `fastapi`,
`pydantic`, `aiosqlite` and `pyyaml`; everything else was `asyncio`,
`subprocess`, `json` and `pathlib`.

## Options considered

**Go.** The strongest fit for the workload — `os/exec`, a goroutine per agent,
`context.Context` propagating cancellation through the DAG, a 15 MB static
binary, one-second builds. Rejected once the UI decision landed: the native GUI
answer required cgo, and cgo removes the fast builds and easy cross-compilation
that were Go's entire advantage over the alternatives.

**Rust.** The lightest result and already present in the repository. Rejected on
cost: porting 10,000 lines of async orchestration is a conceptual rewrite, not a
translation, and child-process cancellation in async Rust — process groups,
orphan reaping — is fiddly work that `asyncio` was absorbing invisibly.

**Python, slimmed.** Serve the built React from FastAPI, drop Tauri, ship with
`uv tool install`. Zero rewrite and it retires two of the three runtimes. Not
chosen because it does not remove the interpreter requirement, which was the
actual defect, and the owner's stated goal included replacing Python.

## Decision

**.NET 10 with C#**, one solution, NativeAOT for release builds.

The deciding argument is not performance. It is that C# is the closest semantic
match to the code being ported, which makes a 10,000-line port tractable rather
than aspirational:

| Python | C# |
| --- | --- |
| `asyncio.create_subprocess_exec` | `Process` + `ProcessStartInfo` |
| `async def` / `await` | `async Task` / `await` |
| `pydantic` models | `record` + `System.Text.Json` |
| `aiosqlite` | `Microsoft.Data.Sqlite` |
| FastAPI + SSE | in-process `IAsyncEnumerable` |
| DAG cancellation | `CancellationToken` |

Second: NativeAOT produces a self-contained executable with no runtime to
install, which is the requirement ADR-003 could not meet.

Third: it is the only candidate whose UI story also satisfies
[ADR-018](ADR-018-AVALONIA-DESKTOP.md). The runtime and the toolkit were not
independent choices.

## Consequences

**The HTTP layer is deleted, not ported.** `api/routes.py` (840 lines) and
`api/schemas.py` (437) existed so a webview could reach the orchestrator over
localhost. `AtlasFlow.Desktop` references `AtlasFlow.Application` directly. No
port, no CORS, no backend-failed-to-start state to render.

**Roughly 40 MB per platform**, against roughly 20 MB for the Rust options. The
comparison that matters is against a Tauri bundle that additionally required an
interpreter, and there this is smaller.

**NativeAOT constrains the dependency list.** Runtime code generation and
unbounded reflection are unavailable. Every dependency must be checked against a
Release publish; a package that works under `dotnet run` and fails at AOT
publish is the most likely way this decision costs unplanned time.

**The Python tooling has to be replaced, not just the backend.**
`scripts/validate_goals.py`, `validate_docs.py`, `generate_sbom.py`,
`attach_evidence.py` and `generate_icons.py` are all Python and all wired into
CI gates. They are out of scope for the initial port and are a known follow-on.

**The port is the risk.** Ten thousand lines of tested behaviour move to a
language where none of it is tested yet. `reference/` keeps the source
side-by-side and `reference/README.md` sets the deletion condition at test
parity, not at "it compiles" — but a partially ported orchestrator that looks
finished is the failure mode to watch for.
