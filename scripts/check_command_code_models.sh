#!/usr/bin/env sh
set -eu

if ! command -v cmd >/dev/null 2>&1; then
  echo "Command Code (cmd) not found." >&2
  exit 1
fi

MODELS="$(cmd --list-models)"
printf '%s\n' "$MODELS"

printf '\nAtlas Flow preferred roster availability:\n'
for pattern in 'deepseek-v4-pro' 'mimo-v2.5-pro' 'luna'; do
  if printf '%s\n' "$MODELS" | grep -qi "$pattern"; then
    printf '  ✓ %s\n' "$pattern"
  else
    printf '  - %s (not exposed by current registry)\n' "$pattern"
  fi
done
