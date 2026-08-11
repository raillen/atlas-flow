#!/usr/bin/env sh
# Drive the packaged application, not the source tree.
#
# The prerequisites are real — a built bundle, a display, xdotool — and this
# script says which one is missing rather than passing quietly. A test that
# reports success because it never ran is worse than no test: it is a claim
# without a check behind it.
#
#   sh scripts/package_smoke.sh && sh scripts/e2e_packaged.sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
[ -f "$ROOT/.atlas-flow/env.sh" ] && . "$ROOT/.atlas-flow/env.sh"

: "${CARGO_TARGET_DIR:=$ROOT/apps/desktop/src-tauri/target}"
export CARGO_TARGET_DIR
PYTHON="${ATLAS_PYTHON:-python3}"

missing=""
BUNDLE="$(find "$CARGO_TARGET_DIR/release/bundle/appimage" -maxdepth 1 \
    -name '*.AppImage' 2>/dev/null | head -n 1)"
[ -n "$BUNDLE" ] || missing="$missing\n  no AppImage — run: sh scripts/package_smoke.sh"
command -v xdotool >/dev/null 2>&1 || missing="$missing\n  xdotool is not installed"
command -v import >/dev/null 2>&1 || \
    printf 'note: ImageMagick "import" is absent; failures will save no screenshot\n' >&2

if [ -z "${DISPLAY:-}" ]; then
    if command -v xvfb-run >/dev/null 2>&1; then
        printf 'No DISPLAY; running under xvfb-run\n'
        exec xvfb-run -a "$0" "$@"
    fi
    missing="$missing\n  no DISPLAY, and xvfb-run is not installed"
fi

if [ -n "$missing" ]; then
    printf 'Cannot drive the packaged application:%b\n' "$missing" >&2
    exit 1
fi

# A window left over from another session would be driven instead of the one
# this run launches, and it has a different configuration.
if command -v pkill >/dev/null 2>&1; then
    pkill -x atlas-flow-desktop 2>/dev/null || true
    sleep 1
fi

printf '=== Driving %s ===\n' "$BUNDLE"
exec "$PYTHON" -m pytest "$ROOT/tests/e2e" -v -p no:cacheprovider "$@"
