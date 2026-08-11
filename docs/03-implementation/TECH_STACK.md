# Technology Stack

One runtime. The previous stack was three — a Python backend, a Node build
toolchain and a Rust webview host — and the packaged app could not start
without `uv` and Python already installed on the user's machine. ADR-017 and
ADR-018 record why that was replaced rather than repaired.

## Runtime

.NET 10 (LTS); C# with nullable reference types enabled and warnings as errors;
`System.Threading.Tasks` throughout; `Microsoft.Data.Sqlite`; `YamlDotNet` for
the Atlas manifests; Git invoked as a child process.

No LLM provider SDK appears anywhere. Model routing stays runtime-discovered
through Command Code and ACP, exactly as before — that property was never a
consequence of the language.

## Desktop

Avalonia 11 targeting Windows and Linux, x86_64. Fluent theme following the
operating system's light/dark variant. Compiled XAML bindings by default. MVVM
via `CommunityToolkit.Mvvm` source generators.

The desktop app references `AtlasFlow.Application` as a library and calls it
in-process. There is no HTTP server, no localhost port and no second process.

## Solution layout

| Project | Owns |
| --- | --- |
| `AtlasFlow.Domain` | Goals, Decisions, Discuss threads, Projects. References nothing. |
| `AtlasFlow.Persistence` | SQLite run state. Git stays canonical (ADR-009). |
| `AtlasFlow.Protocols` | ACP, MCP and AG-UI — one folder each. |
| `AtlasFlow.Orchestration` | Planner, execution, harness, runners, routing, verification. |
| `AtlasFlow.Application` | Use cases and composition. |
| `AtlasFlow.Desktop` | The Avalonia workspace. |
| `AtlasFlow.Cli` | `atlas` — the same engine without a window. Never references Desktop. |

The boundaries are the ones the Python package already had. They were not the
problem, so the port did not relitigate them.

## Protocols

Unchanged, and deliberately so. AG-UI = UI ↔ orchestration. ACP = Atlas Harness
↔ coding agents. MCP = agents/runtime ↔ external tools.

AG-UI is now an in-process event stream (`IAsyncEnumerable<AgUiEvent>`) rather
than server-sent events over localhost. The event *model* did not change; only
the transport did, and the transport existed to cross a process boundary that
no longer exists.

## Development

Command Code. Models: DeepSeek V4 Pro, MiMo V2.5 Pro, GPT-5.6 Luna when the
runtime registry exposes it.

## Packaging

NativeAOT, self-contained, per platform. `deb` and Flatpak on Linux, MSI on
Windows. Nothing to install alongside it. See
[PACKAGING.md](PACKAGING.md).

## What this costs

Written down because a stack document that lists only advantages is marketing:

- **Bigger binary than the alternatives considered.** A NativeAOT Avalonia
  build lands near 40 MB against roughly 20 MB for Rust with Slint. It is still
  the smaller number against a Tauri bundle that additionally required a Python
  interpreter to be present.
- **No `axe-core` equivalent.** The React build had 343 lines of automated
  accessibility assertions over rendered DOM. Avalonia exposes UI Automation and
  AT-SPI, which is a real accessibility surface, but the automated audit that
  caught two contrast failures has no direct replacement. See
  [ACCESSIBILITY.md](../02-ui-ux/ACCESSIBILITY.md).
- **Windows re-enters scope.** It was a recorded non-goal on P06, P09 and P10.
  ADR-018 reopens it, and the cost is a second platform to build, sign and test.
