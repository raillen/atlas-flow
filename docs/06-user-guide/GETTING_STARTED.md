# Getting Started

## Prerequisites

- Python 3.12+ with `uv`
- Node.js 24+ with `pnpm` 11+
- Git (task isolation uses real worktrees)
- Rust toolchain — only to build the desktop shell
- Command Code CLI (`cmd`) — optional; without it, model discovery reports a
  degraded registry and routing falls back to the policy roster

## Install

```bash
git clone <repo-url> atlas-flow
cd atlas-flow
uv sync --project backend
pnpm install
```

If your checkout is on a mount with `noexec`, point build tooling elsewhere:
`export CARGO_TARGET_DIR=~/.cache/atlas-flow-target`, and create the Python
environment outside the mount with `UV_PROJECT_ENVIRONMENT`. Cargo executes
build scripts out of its target directory and Python loads compiled extensions
from the virtualenv; a `noexec` mount fails both with a bare permission error.

## Run it

```bash
# Terminal 1 — backend
uv run --project backend uvicorn atlas_flow.api.app:create_app --factory --reload

# Terminal 2 — desktop client
pnpm --filter @atlas-flow/desktop dev
```

Open **http://localhost:1420**:

- **Discuss** — conversation that can become ADRs and a Decision Ledger
- **Plan** — the Goals in Git, and the task DAG a run will execute
- **Build** — live task, attempt and event state, plus agent narration
- **Review** — gate verdicts, evidence, and which model each role routes to
- **Project** — canonical documentation, and the backend process if you launched
  the packaged desktop app

In the packaged app the Project tab can start and stop the backend for you. It
does not start one at launch, so a backend you are already running by hand keeps
the port.

## Open a different project

Atlas Flow orchestrates whatever project it is opened on. Point it at one:

```bash
ATLAS_FLOW_PROJECT_ROOT=/path/to/your/project \
  uv run --project backend uvicorn atlas_flow.api.app:create_app --factory
```

Without that variable the project root is the nearest ancestor of the working
directory containing `PROJECT_MANIFEST.yaml`. The project must be a Project
Atlas 0.1.x project — see
[the compatibility matrix](../09-references/COMPATIBILITY_MATRIX.md) for exactly
what is required.

Operational state lands in `<project>/.atlas-flow/`, which ignores itself, so
running Atlas Flow never makes your repository look dirty. Deleting it loses run
history and nothing else: canonical truth stays in Git.

## Validate

```bash
sh scripts/validate_all.sh          # docs, Goals, Command Code registries
uv run --project backend ruff check .
uv run --project backend mypy
uv run --project backend pytest
pnpm run typecheck && pnpm run lint && pnpm run test
```

`scripts/package_smoke.sh` builds the desktop bundle and checks what came out.

## Where to look next

- [Running Goals](RUNNING_GOALS.md) — what a run actually does
- [Model routing](MODEL_ROUTING.md) — which model does what, and why
- [Recovery](RECOVERY.md) — what happens after a crash
- `docs/ATLAS.md` — the full documentation map
