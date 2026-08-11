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
if [ -f "$ROOT/.atlas-flow/env.sh" ]; then
  . "$ROOT/.atlas-flow/env.sh"
fi
: "${CARGO_TARGET_DIR:=$ROOT/apps/desktop/src-tauri/target}"
export CARGO_TARGET_DIR

BUNDLE_DIR="$CARGO_TARGET_DIR/release/bundle/deb"
APPIMAGE_DIR="$CARGO_TARGET_DIR/release/bundle/appimage"

# linuxdeploy is itself an AppImage, and mounting one needs FUSE. Extracting
# instead works on machines and CI runners that have no FUSE at all, which is
# what made this bundle unverifiable before.
export APPIMAGE_EXTRACT_AND_RUN=1

VERIFY_ONLY=0
[ "${1:-}" = "--verify-only" ] && VERIFY_ONLY=1

if [ "$VERIFY_ONLY" -eq 0 ]; then
  printf '=== Building the desktop bundle ===\n'
  VITE_ENTRY="$(node -e "const fs=require('fs'); const path=require('path'); const pkg=require.resolve('vite/package.json', { paths: ['$ROOT/apps/desktop'] }); const data=JSON.parse(fs.readFileSync(pkg, 'utf8')); process.stdout.write(path.join(path.dirname(pkg), data.bin.vite));")"
  TAURI_ENTRY="$(node -e "process.stdout.write(require.resolve('@tauri-apps/cli/tauri.js', { paths: ['$ROOT/apps/desktop'] }));")"
  ( cd "$ROOT/apps/desktop" && node "$VITE_ENTRY" build )
  ( cd "$ROOT/apps/desktop" && node "$TAURI_ENTRY" build --bundles deb,appimage )
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

APPIMAGE="$(find "$APPIMAGE_DIR" -maxdepth 1 -name '*.AppImage' 2>/dev/null | head -n 1)"
if [ -n "$APPIMAGE" ]; then
  printf 'appimage: %s\n' "$APPIMAGE"
  # An AppImage that cannot unpack itself is not an AppImage, so the check is
  # that it opens rather than that a file of that name exists.
  EXTRACT_DIR="$(mktemp -d)"
  if ( cd "$EXTRACT_DIR" && "$APPIMAGE" --appimage-extract >/dev/null 2>&1 ) \
      && [ -x "$EXTRACT_DIR/squashfs-root/usr/bin/atlas-flow-desktop" ]; then
    printf '  ok   appimage unpacks and carries the executable\n'
  else
    printf '  BROKEN appimage does not unpack into a runnable tree\n' >&2
    FAILED=1
  fi
  rm -rf "$EXTRACT_DIR"
else
  printf 'No .AppImage produced in %s\n' "$APPIMAGE_DIR" >&2
  FAILED=1
fi

printf '\n=== Release artefacts ===\n'

# Both are produced beside the package, so an artefact and the record of what
# is inside it never drift apart.
PYTHON="${ATLAS_PYTHON:-python3}"
if ! "$PYTHON" "$ROOT/scripts/generate_sbom.py" "$BUNDLE_DIR/sbom.cyclonedx.json"; then
  printf 'SBOM generation failed\n' >&2
  FAILED=1
fi

if command -v sha256sum >/dev/null 2>&1; then
  ( cd "$BUNDLE_DIR" && cp "$APPIMAGE" . 2>/dev/null || true )
  ( cd "$BUNDLE_DIR" && sha256sum ./*.deb ./*.AppImage ./sbom.cyclonedx.json > SHA256SUMS )
  printf 'checksums: %s\n' "$BUNDLE_DIR/SHA256SUMS"
else
  printf 'sha256sum not available; no checksums written\n' >&2
  FAILED=1
fi

# Signing covers SHA256SUMS rather than each artefact: one signature over the
# list of digests is what a verifier actually checks, and it cannot be
# sidestepped by swapping a file the list already names.
#
# ATLAS_SIGNING_KEY names a GPG key. Without one the signature is skipped and
# said so out loud — an unsigned release that claims to be signed is worse
# than one that admits it is not.
if [ -n "${ATLAS_SIGNING_KEY:-}" ]; then
  if command -v gpg >/dev/null 2>&1; then
    if gpg --batch --yes --local-user "$ATLAS_SIGNING_KEY" \
        --armor --detach-sign --output "$BUNDLE_DIR/SHA256SUMS.asc" \
        "$BUNDLE_DIR/SHA256SUMS"; then
      printf 'signature: %s\n' "$BUNDLE_DIR/SHA256SUMS.asc"
      if gpg --batch --verify "$BUNDLE_DIR/SHA256SUMS.asc" \
          "$BUNDLE_DIR/SHA256SUMS" 2>/dev/null; then
        printf '  ok   signature verifies against the checksums\n'
      else
        printf '  BROKEN signature does not verify\n' >&2
        FAILED=1
      fi
    else
      printf 'signing failed with key %s\n' "$ATLAS_SIGNING_KEY" >&2
      FAILED=1
    fi
  else
    printf 'ATLAS_SIGNING_KEY is set but gpg is not installed\n' >&2
    FAILED=1
  fi
else
  printf 'unsigned: set ATLAS_SIGNING_KEY to a gpg key id to sign SHA256SUMS\n'
fi

if [ "$FAILED" -eq 0 ]; then
  printf '\nPackaging smoke test PASSED.\n'
else
  printf '\nPackaging smoke test FAILED.\n' >&2
  exit 1
fi
