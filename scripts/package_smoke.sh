#!/usr/bin/env sh
# Build the desktop bundle and check that what came out is installable.
#
# "It compiled" is not the same as "it packages": the bundle has to contain the
# binary, a desktop entry and icons, and those are produced by a different part
# of the toolchain than the one that compiles Rust.
#
# Usage: sh scripts/package_smoke.sh [--verify-only]
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${CARGO_TARGET_DIR:=$ROOT/apps/desktop/src-tauri/target}"
export CARGO_TARGET_DIR

BUNDLE_DIR="$CARGO_TARGET_DIR/release/bundle/deb"
VERIFY_ONLY=0
[ "${1:-}" = "--verify-only" ] && VERIFY_ONLY=1

if [ "$VERIFY_ONLY" -eq 0 ]; then
  printf '=== Building the desktop bundle ===\n'
  pnpm --filter @atlas-flow/desktop build
  pnpm --filter @atlas-flow/desktop tauri build --bundles deb
fi

printf '\n=== Verifying the bundle ===\n'

PACKAGE="$(find "$BUNDLE_DIR" -maxdepth 1 -name '*.deb' 2>/dev/null | head -n 1)"
if [ -z "$PACKAGE" ]; then
  printf 'No .deb produced in %s\n' "$BUNDLE_DIR" >&2
  exit 1
fi
printf 'package: %s\n' "$PACKAGE"

# Tauri leaves the staging tree beside the archive; checking it avoids
# depending on dpkg being installed on the machine that builds.
STAGE="$(find "$BUNDLE_DIR" -maxdepth 1 -type d -name '*_amd64' | head -n 1)"
if [ -z "$STAGE" ]; then
  printf 'No staging tree beside the package\n' >&2
  exit 1
fi

FAILED=0
require() {
  if [ -e "$1" ]; then
    printf '  ok   %s\n' "$2"
  else
    printf '  MISSING %s\n' "$2" >&2
    FAILED=1
  fi
}

require "$STAGE/data/usr/bin/atlas-flow-desktop" "executable"
require "$STAGE/data/usr/share/applications" "desktop entry"
require "$STAGE/data/usr/share/icons/hicolor/128x128/apps" "icons"
require "$STAGE/control/control" "control metadata"

if [ "$FAILED" -eq 0 ]; then
  printf '\nPackaging smoke test PASSED.\n'
else
  printf '\nPackaging smoke test FAILED.\n' >&2
  exit 1
fi
