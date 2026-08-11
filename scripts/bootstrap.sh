#!/usr/bin/env sh
# Prepare a checkout so every gate can actually be run.
#
# An independent reviewer could not run the local gates at all: the Python
# environment could not load its compiled dependencies and the tool binaries
# refused to execute. Both have the same cause — a checkout on a filesystem
# mounted `noexec`, which is how removable and secondary disks are mounted by
# default on most Linux desktops. Cargo executes build scripts out of its
# target directory, Python loads compiled extensions from the virtualenv, and
# pnpm runs tools through shim scripts; all three fail with a bare permission
# error that names none of this.
#
# So the environment is placed somewhere that permits execution, and the
# resolved locations are written to .atlas-flow/env.sh for the other scripts
# to source. Gates that cannot be run are gates that cannot be trusted.
#
#   sh scripts/bootstrap.sh && sh scripts/run_gates.sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/atlas-flow"
ENV_FILE="$ROOT/.atlas-flow/env.sh"

# Can this filesystem execute a file? Ask it rather than guessing from the
# mount table, which does not exist in the same form everywhere.
can_execute() {
    probe="$1/.atlas-exec-probe"
    printf '#!/bin/sh\nexit 0\n' > "$probe" 2>/dev/null || return 1
    chmod +x "$probe" 2>/dev/null || { rm -f "$probe"; return 1; }
    if "$probe" >/dev/null 2>&1; then
        rm -f "$probe"
        return 0
    fi
    rm -f "$probe"
    return 1
}

mkdir -p "$ROOT/.atlas-flow"

if can_execute "$ROOT"; then
    printf 'checkout permits execution; using in-tree locations\n'
    VENV="$ROOT/backend/.venv"
    TARGET="$ROOT/apps/desktop/src-tauri/target"
else
    printf 'checkout is on a noexec filesystem; relocating build environments\n'
    printf '  (run tools through scripts/run_gates.sh, or source %s)\n' "$ENV_FILE"
    VENV="$CACHE/venv"
    TARGET="$CACHE/target"
    mkdir -p "$CACHE"
fi

printf '\n=== Python environment ===\n'
if ! command -v uv >/dev/null 2>&1; then
    printf 'uv is required: https://docs.astral.sh/uv/\n' >&2
    exit 1
fi
UV_PROJECT_ENVIRONMENT="$VENV" uv sync --project "$ROOT/backend" --all-extras

PYTHON="$VENV/bin/python"
[ -x "$PYTHON" ] || PYTHON="$VENV/Scripts/python.exe"
if ! "$PYTHON" -c "import atlas_flow, aiosqlite, pydantic_core" >/dev/null 2>&1; then
    printf 'The environment at %s cannot import the backend.\n' "$VENV" >&2
    "$PYTHON" -c "import atlas_flow, aiosqlite, pydantic_core" >&2 || true
    exit 1
fi
printf 'ok: %s can import atlas_flow with its compiled dependencies\n' "$PYTHON"

printf '\n=== Node environment ===\n'
if command -v pnpm >/dev/null 2>&1; then
    ( cd "$ROOT" && pnpm install --frozen-lockfile )
    printf 'ok: node_modules installed\n'
else
    printf 'pnpm not found; skipping the frontend gates\n' >&2
fi

cat > "$ENV_FILE" <<EOF
# Written by scripts/bootstrap.sh. Source this to run the gates by hand.
export ATLAS_PYTHON="$PYTHON"
export UV_PROJECT_ENVIRONMENT="$VENV"
export CARGO_TARGET_DIR="$TARGET"
EOF

printf '\nWrote %s\n' "$ENV_FILE"
printf 'Next: sh scripts/run_gates.sh\n'
