# Project Atlas Compatibility Matrix

What Atlas Flow can open, and what it requires of the project it opens.

## Framework versions

| project-atlas-framework | Support |
| --- | --- |
| 0.1.x | Supported |
| anything else | Refused at load with an actionable error, not degraded silently |

The version is read from the opened project's `PROJECT_MANIFEST.yaml`, never
from the process working directory — those are unrelated once Atlas Flow is
installed rather than run from its own checkout.

## Required manifests

`resolve_project` refuses a project missing any of these. There is no partial
mode: a half-loaded project would produce runs whose provenance nobody could
reconstruct.

| Path | Provides |
| --- | --- |
| `PROJECT_MANIFEST.yaml` | Framework version, project id and name |
| `.ai/context/project-profile.yaml` | Project id, types, languages, risk profile |
| `.ai/goals/**/*.yaml` | Goals, grouped into phases by their `phase` field |
| `.ai/agents/manifest.yaml` | Available agent roles |
| `.ai/skills/manifest.yaml` | Available skills |
| `.ai/recipes/manifest.yaml` | Available recipes |
| `.ai/orchestration/model-policy.yaml` | Model roster and routing principles |
| `.ai/orchestration/autonomy-policy.yaml` | Autonomy modes and the project's current mode |
| `.ai/orchestration/orchestrator.yaml` | Execution settings (isolation, worktree strategy) |
| `.ai/orchestration/fallbacks.yaml` | Retry and escalation policy |

Optional: `.ai/orchestration/mcp-servers.yaml` (absent means no MCP servers are
forwarded).

## Validated project categories

Atlas Flow is generic by intent, so genericity is tested rather than asserted.
`tests/integration/test_dogfooding.py` builds each of these from scratch and
runs a Goal end to end against it:

| Category | Fixture | Shape it exercises |
| --- | --- | --- |
| Library | `pigment` (Python) | Two phases with a cross-phase dependency, no UI |
| Web application | `ledgerly` (TypeScript, SQL) | Multiple types, three acceptance criteria in one Goal |
| CLI tool | `quill` (Rust) | Single phase, minimal manifest set |

Each is checked for the same things: the API serves that project's Goals,
a run reaches SUCCEEDED tasks with build evidence, every event is attributed to
that project's id, and operational state lands in that project's
`.atlas-flow/` rather than being shared or leaked into Atlas Flow's own
directory.

Doing this found two real defects: the project id was hardcoded to `atlas-flow`
in five places, and the project root was resolved by walking up from the
installed package, so an installed Atlas Flow would have served its own Goals to
somebody else's project.

## What is not covered

- Projects with no Git repository. Task isolation uses git worktrees, so a
  non-Git project can be read but not executed against.
- Monorepos with several `PROJECT_MANIFEST.yaml` files; the nearest ancestor
  wins, and there is no way to choose a different one except
  `ATLAS_FLOW_PROJECT_ROOT`.
- Framework versions beyond 0.1.x, which do not exist yet.
