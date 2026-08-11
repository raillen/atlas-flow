# Reference implementation — to be deleted

This directory holds the Python and TypeScript implementation that the C# port
is being written *from*. It is not built, not tested, and not shipped.

| Path | Was | Ported to |
| --- | --- | --- |
| `python-backend/` | `backend/atlas_flow` — 10,051 lines | `src/AtlasFlow.*` |
| `tauri-desktop/` | `apps/desktop` — React + Tauri shell | `src/AtlasFlow.Desktop` |
| `ts-packages/` | `packages/{ui,domain-types,ag-ui-client}` | `src/AtlasFlow.Domain`, `src/AtlasFlow.Desktop` |
| `python-tests/` | `tests/{unit,integration,e2e,reliability}` | `tests/AtlasFlow.*.Tests` |

It exists here rather than only in Git history because a port is read
side-by-side, and `git show 61bc9c8:backend/...` for every file is friction that
buys nothing. The tradeoff is that the branch temporarily contains two stacks.

**Delete this directory when the port is complete.** A reference implementation
that outlives its port stops being a reference and starts being a second source
of truth — and the one nobody is maintaining is the one somebody will read.

The condition for deletion is not "the C# builds". It is that every behaviour
covered by `python-tests/` has an equivalent test under `tests/`, passing.
