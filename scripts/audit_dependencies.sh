#!/usr/bin/env sh
# Check every ecosystem's dependencies against its advisory database.
#
# Runnable locally, not only in CI: a review that cannot reproduce an audit has
# to take it on trust, which is the opposite of what an audit is for.
#
# Being unable to reach an advisory database is reported as a failure rather
# than skipped. "I could not check" and "there is nothing to find" are
# different answers, and only one of them is evidence.
#
#   sh scripts/audit_dependencies.sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FAILED=""
note() { printf '\n=== %s ===\n' "$1"; }
fail() { printf '%s\n' "$1" >&2; FAILED="$FAILED\n  $1"; }

note "Python (pip-audit)"
if command -v uv >/dev/null 2>&1; then
    REQUIREMENTS="$(mktemp)"
    # The project itself is excluded: it is the thing being audited, not a
    # dependency, and building it from a requirements file fails anyway.
    if uv export --project backend --no-hashes --no-emit-project \
        --format requirements-txt > "$REQUIREMENTS" 2>/dev/null; then
        if uvx pip-audit --strict --no-deps -r "$REQUIREMENTS"; then
            printf 'python: no known vulnerabilities\n'
        else
            fail "python: advisories found, or the database was unreachable"
        fi
    else
        fail "python: could not export the locked requirements"
    fi
    rm -f "$REQUIREMENTS"
else
    fail "python: uv is not installed, so nothing was audited"
fi

note "Node (pnpm audit)"
if command -v pnpm >/dev/null 2>&1; then
    if pnpm audit --audit-level=high; then
        printf 'node: no advisories at high or above\n'
    else
        fail "node: advisories found, or the registry was unreachable"
    fi
else
    fail "node: pnpm is not installed, so nothing was audited"
fi

note "Rust (cargo audit)"
if command -v cargo-audit >/dev/null 2>&1 || cargo audit --version >/dev/null 2>&1; then
    AUDIT_OUT="$(mktemp)"
    if cargo audit --file apps/desktop/src-tauri/Cargo.lock > "$AUDIT_OUT" 2>&1; then
        # cargo audit exits 0 for "unmaintained" warnings and non-zero only for
        # vulnerabilities. Warnings are still reported here: a dependency
        # nobody maintains is a finding, even when nothing can be done about it
        # from this repository.
        WARNINGS="$(grep -c '^ID: *RUSTSEC' "$AUDIT_OUT" 2>/dev/null || echo 0)"
        printf 'rust: no vulnerabilities'
        if [ "$WARNINGS" -gt 0 ]; then
            printf ', %s unmaintained-crate warning(s)' "$WARNINGS"
        fi
        printf '\n'
    else
        cat "$AUDIT_OUT" >&2
        fail "rust: vulnerabilities found, or the database was unreachable"
    fi
    rm -f "$AUDIT_OUT"
else
    fail "rust: cargo-audit is not installed (cargo install cargo-audit)"
fi

if [ -z "$FAILED" ]; then
    printf '\nDependency audit PASSED.\n'
    exit 0
fi
printf '\nDependency audit FAILED:%b\n' "$FAILED" >&2
exit 1
