#!/usr/bin/env sh
# Run every gate this repository claims, and report which ones failed.
#
# One entry point on purpose: a reviewer should not have to reconstruct six
# commands from prose, and a gate that is hard to run is a gate that quietly
# stops being run. Node tools are invoked through their JavaScript entry points
# rather than the `node_modules/.bin` shims, so they work on checkouts where
# those shims cannot be executed.
#
#   sh scripts/bootstrap.sh && sh scripts/run_gates.sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
[ -f "$ROOT/.atlas-flow/env.sh" ] && . "$ROOT/.atlas-flow/env.sh"

if [ -z "${ATLAS_PYTHON:-}" ]; then
    printf 'No environment found. Run: sh scripts/bootstrap.sh\n' >&2
    exit 1
fi

FAILED=""
run() {
    label="$1"
    shift
    printf '\n=== %s ===\n' "$label"
    if "$@"; then
        printf '%s: PASS\n' "$label"
    else
        printf '%s: FAIL\n' "$label" >&2
        FAILED="$FAILED\n  $label"
    fi
}

# Resolve a Node CLI to its script, so it never needs the executable bit.
# `require.resolve` refuses subpaths a package does not export, so the plain
# path is tried too; between them every tool here resolves.
node_bin() {
    resolved="$(node -p "require.resolve('$1')" 2>/dev/null || true)"
    if [ -n "$resolved" ] && [ -f "$resolved" ]; then
        printf '%s' "$resolved"
        return 0
    fi
    if [ -f "$ROOT/node_modules/$1" ]; then
        printf '%s' "$ROOT/node_modules/$1"
        return 0
    fi
    return 0
}

run "Python lint"      "$ATLAS_PYTHON" -m ruff check .
run "Python types"     "$ATLAS_PYTHON" -m mypy
run "Python tests"     "$ATLAS_PYTHON" -m pytest

if command -v node >/dev/null 2>&1; then
    TSC="$(node_bin typescript/bin/tsc)"
    ESLINT="$(node_bin eslint/bin/eslint.js)"
    VITEST="$(node_bin vitest/vitest.mjs)"
    for tool in TSC ESLINT VITEST; do
        eval "value=\$$tool"
        [ -n "$value" ] || printf 'could not resolve %s; skipping it\n' "$tool" >&2
    done
    if [ -n "$TSC" ]; then
        run "TypeScript build" node "$TSC" -b --force \
            packages/domain-types packages/ag-ui-client packages/ui apps/desktop
    fi
    [ -n "$ESLINT" ] && run "JS lint" node "$ESLINT" .
    [ -n "$VITEST" ] && run "JS tests" node "$VITEST" run
else
    printf '\nnode not found; skipping the frontend gates\n' >&2
fi

if command -v cargo >/dev/null 2>&1; then
    run "Desktop format" cargo fmt --check --manifest-path apps/desktop/src-tauri/Cargo.toml
    run "Desktop lint" cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml \
        --all-targets -- -D warnings
else
    printf '\ncargo not found; skipping the desktop shell gates\n' >&2
fi

run "Docs and Goals" env ATLAS_PYTHON="$ATLAS_PYTHON" sh "$ROOT/scripts/validate_all.sh"

if [ -z "$FAILED" ]; then
    printf '\nAll gates PASSED.\n'
    exit 0
fi
printf '\nFAILED gates:%b\n' "$FAILED" >&2
exit 1
