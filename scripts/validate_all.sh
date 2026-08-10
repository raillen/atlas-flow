#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=0

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

run "Docs validation"              python3 "$ROOT/scripts/validate_docs.py"
run "Goals validation"             python3 "$ROOT/scripts/validate_goals.py"
run "Command Code discoverability" "$ROOT/scripts/validate_command_code.sh"

if [ "$FAILED" -eq 0 ]; then
  printf '\nAll validations PASSED.\n'
  exit 0
else
  printf '\nSome validations FAILED.\n' >&2
  exit 1
fi
