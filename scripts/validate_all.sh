#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=0

# The validators import atlas_flow, so they need the backend environment rather
# than whatever python3 happens to be on PATH.
if [ -n "${ATLAS_PYTHON:-}" ]; then
  PYTHON="$ATLAS_PYTHON"
elif [ -x "$ROOT/backend/.venv/bin/python" ]; then
  PYTHON="$ROOT/backend/.venv/bin/python"
elif command -v uv >/dev/null 2>&1; then
  PYTHON="uv run --project $ROOT/backend python"
else
  PYTHON="python3"
fi

run() {
  label="$1"
  shift
  printf '\n=== %s ===\n' "$label"
  if "$@"; then
    printf '=== %s: PASS ===\n\n' "$label"
  else
    printf '=== %s: FAIL ===\n\n' "$label" >&2
    FAILED=1
  fi
}

run "Docs validation"              $PYTHON "$ROOT/scripts/validate_docs.py"
run "Goals validation"             $PYTHON "$ROOT/scripts/validate_goals.py"
run "Command Code discoverability" "$ROOT/scripts/validate_command_code.sh"

if [ "$FAILED" -eq 0 ]; then
  printf '\nAll validations PASSED.\n'
  exit 0
else
  printf '\nSome validations FAILED.\n' >&2
  exit 1
fi
