# Repository Structure

```text
atlas-flow/
├── AGENTS.md
├── ENTRYPOINT.md
├── PROJECT_MANIFEST.yaml
├── PROJECT_STATE.md
├── AtlasFlow.slnx
├── Directory.Build.props        # nullable, warnings-as-errors, analyzers
├── Directory.Packages.props     # every package version, declared once
├── global.json                  # pinned SDK
├── .editorconfig                # style and analyzer severities
├── docs/
├── .ai/
├── .commandcode/
├── src/
│   ├── AtlasFlow.Domain/{Goals,Decisions,Discuss,Projects}/
│   ├── AtlasFlow.Persistence/
│   ├── AtlasFlow.Protocols/{Acp,Mcp,AgUi}/
│   ├── AtlasFlow.Orchestration/
│   │   ├── Planner/ Execution/ Harness/ Runners/
│   │   └── Routing/ Verification/ Workforce/ Context/
│   ├── AtlasFlow.Application/
│   ├── AtlasFlow.Desktop/{Views,ViewModels,Controls,Theme}/
│   └── AtlasFlow.Cli/
├── tests/
│   ├── AtlasFlow.Domain.Tests/
│   ├── AtlasFlow.Persistence.Tests/
│   ├── AtlasFlow.Protocols.Tests/
│   ├── AtlasFlow.Orchestration.Tests/
│   ├── AtlasFlow.Desktop.Tests/          # Avalonia.Headless
│   └── AtlasFlow.Integration.Tests/
├── reference/                            # being ported from; delete when done
├── schemas/
└── scripts/
```

## Rules the layout encodes

**`AtlasFlow.Domain` references nothing.** Not the database, not a wire format,
not a logger. If a Goal or a Decision cannot be expressed without SQLite or
JSON-RPC, the type is wrong and the compiler is the one that says so.

**`AtlasFlow.Cli` never references `AtlasFlow.Desktop`.** CI runs the release
gates through the CLI, and a gate that needs a display server is a gate that
cannot run headless.

**There is no `AtlasFlow.Api`.** The Python build had `api/routes.py` (840
lines) and `api/schemas.py` (437) so that a webview could reach the orchestrator
over localhost. The Avalonia app references `AtlasFlow.Application` directly.
That layer was a consequence of the process boundary, and the boundary is gone.

**`reference/` is temporary.** It holds the Python and TypeScript sources the
port reads from. Its deletion condition is written in
[`reference/README.md`](../../reference/README.md) and is not "the C# builds".
