# Atlas Flow

**Atlas Flow** is the reference orchestration runtime for the Project Atlas Framework.

It turns durable project knowledge and locked Goals into observable, multi-agent execution while keeping Git—not chat history, an LLM provider, or the orchestrator database—as the canonical source of truth.

> **This branch is the C# port.** Atlas Flow previously shipped as three
> runtimes: a Python backend, a Node build toolchain and a Rust webview host.
> The packaged app could not start unless `uv` and Python were already installed
> on the user's machine. This branch replaces all three with one .NET solution
> and an Avalonia window. See [ADR-017](docs/07-decisions/ADR-017-DOTNET-RUNTIME.md)
> and [ADR-018](docs/07-decisions/ADR-018-AVALONIA-DESKTOP.md).
>
> The port is **not complete**. `reference/` holds the Python and TypeScript
> implementation it is being written from.

## Product thesis

```text
Idea
  ↓
Discuss
  ↓
Decisions + Project Draft
  ↓
Project Atlas documentation
  ↓
Goals
  ↓
Task DAG
  ↓
Agent/Skill resolution
  ↓
Model routing
  ↓
Isolated execution
  ↓
Verification + Evidence
  ↓
Review
  ↓
Release
```

## Key properties
- Project-type and stack agnostic.
- Project Atlas-native, but the framework remains independently usable.
- Goal-first rather than prompt-first.
- Agents are abstract roles; models and harnesses are replaceable.
- Git is durable memory; SQLite stores operational run state only.
- AG-UI for user-facing agent event streaming.
- ACP preferred for coding-agent interoperability.
- MCP for tools and external services.
- Command Code is the development harness for this project.
- DeepSeek V4 Pro and MiMo V2.5 Pro are the primary development models.
- GPT-5.6 Luna is the preferred efficient third model when present in the active Command Code registry.
- One runtime. Nothing to install alongside the application.

## Entry points
- `ENTRYPOINT.md`
- `docs/ATLAS.md`
- `PROJECT_STATE.md`
- `.ai/goals/`
- `.ai/orchestration/`
- `.commandcode/`

## Requirements

.NET 10 SDK. On Arch Linux:

```sh
sudo pacman -S dotnet-sdk
```

Nothing else. Git must be on `PATH`, as it always had to be — Atlas Flow drives
worktrees.

## Running it

```sh
dotnet run --project src/AtlasFlow.Desktop
```

One process, one window. There is no backend to start in another terminal and
no port to open: the desktop app references `AtlasFlow.Application` and calls
the orchestrator in-process.

Atlas Flow opens any directory and first reports its Project Atlas mode. An
external project can be explored and discussed; after an authorized adaptation,
the workspace enables **Plan → Run → Review**. A Goal is planned into a
reviewable snapshot, locked, executed in isolated worktrees and followed through
evidence.

The same engine without a window:

```sh
dotnet run --project src/AtlasFlow.Cli -- --root . validate --json
dotnet run --project src/AtlasFlow.Cli -- --root . context "goal execution" --json
dotnet run --project src/AtlasFlow.Cli -- --root . docs build --visibility internal
```

See [Atlas CLI](docs/06-user-guide/ATLAS_CLI.md) and the [v2 foundation](docs/03-implementation/ATLAS_FLOW_V2_FOUNDATION.md).

Run every check with:

```sh
sh scripts/validate_all.sh
```

## Current state

**The C# port is a scaffold that builds.** Verified on Linux, 2026-08-11:
`dotnet restore` and `dotnet build` are clean with warnings-as-errors, the
NativeAOT publish succeeds, and the published 20 MB binary opens a window.

That is the toolchain, not the product. **Zero tests exist**, no orchestration
logic has been ported, and nothing has been attempted on Windows.

What the Python implementation in `reference/` does today, and what the port
must reach: the Discuss → Goal → DAG → isolated execution → evidence path runs
end to end, on durable state, with a real ACP client and real git worktrees.

Goal completion is enforced: `scripts/validate_goals.py` fails CI if a Goal
claims DONE without passing evidence for every required gate. That script is
itself Python and is on the list of things the port has to replace.

The largest open gap in the product, unchanged by the port, is that **no LLM is
ever invoked** — the router picks model identifiers, but the CLI and ACP runners
are the only paths that perform work.

See `PROJECT_STATE.md` for per-Goal status and `VALIDATION_REPORT.md` for the
current check results and the full list of known gaps.
