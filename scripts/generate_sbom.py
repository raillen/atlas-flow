#!/usr/bin/env python3
"""Generate a CycloneDX SBOM for every ecosystem Atlas Flow ships from.

Read from the lockfiles rather than from an installed environment: a lockfile
is what a release is actually built from, it is the same on every machine, and
it does not need the network or a working toolchain to inspect. An SBOM that
depends on the machine that generated it describes that machine, not the
release.

Usage: python scripts/generate_sbom.py [output.json]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "sbom.cyclonedx.json"

# pnpm-lock package keys look like "  '@scope/name@1.2.3':" or "  name@1.2.3:",
# sometimes with a peer-dependency suffix in parentheses.
PNPM_ENTRY = re.compile(
    r"^ {2}'?(?P<name>@?[^@'\s][^@']*)@(?P<version>[0-9][^'(\s:]*)"
)


def python_components(lock: Path) -> list[dict[str, Any]]:
    if not lock.is_file():
        return []
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    return [
        _component("pypi", package["name"], str(package.get("version", "")))
        for package in data.get("package", [])
        if package.get("name")
    ]


def rust_components(lock: Path) -> list[dict[str, Any]]:
    if not lock.is_file():
        return []
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    return [
        _component("cargo", package["name"], str(package.get("version", "")),
                   digest=package.get("checksum"))
        for package in data.get("package", [])
        if package.get("name")
    ]


def node_components(lock: Path) -> list[dict[str, Any]]:
    """Read the `packages:` section without a YAML dependency.

    The lockfile is large and its package keys are a well-defined single-line
    shape, so a targeted scan is more honest than pulling in a parser to read
    two fields out of it.
    """
    if not lock.is_file():
        return []
    components: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    in_packages = False
    for line in lock.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            # Blank lines separate entries; they do not end the section.
            continue
        if not line.startswith(" "):
            in_packages = line.startswith("packages:")
            continue
        if not in_packages:
            continue
        match = PNPM_ENTRY.match(line)
        if match is None:
            continue
        # Integrity lives on the next lines; the key alone identifies the
        # package, which is what a bill of materials needs.
        key = (match.group("name"), match.group("version"))
        if key in seen:
            continue
        seen.add(key)
        components.append(_component("npm", *key))
    return components


def _component(
    ecosystem: str, name: str, version: str, digest: str | None = None
) -> dict[str, Any]:
    component: dict[str, Any] = {
        "type": "library",
        "name": name,
        "version": version,
        "purl": f"pkg:{ecosystem}/{name}@{version}",
    }
    if digest:
        component["hashes"] = [{"alg": "SHA-256", "content": digest}]
    return component


def build_sbom() -> dict[str, Any]:
    components = (
        python_components(ROOT / "backend" / "uv.lock")
        + node_components(ROOT / "pnpm-lock.yaml")
        + rust_components(ROOT / "apps" / "desktop" / "src-tauri" / "Cargo.lock")
    )
    components.sort(key=lambda c: (c["purl"]))

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "component": {
                "type": "application",
                "name": "atlas-flow",
                "version": _project_version(),
            },
            "tools": [{"name": "scripts/generate_sbom.py"}],
        },
        "components": components,
    }


def _project_version() -> str:
    manifest = ROOT / "PROJECT_MANIFEST.yaml"
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version:"):
                return line.split(":", 1)[1].strip().strip('"')
    return "0.0.0"


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    sbom = build_sbom()
    if not sbom["components"]:
        print("No lockfiles found; nothing to describe.", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(sbom, indent=2, sort_keys=False) + "\n"
    output.write_text(payload, encoding="utf-8")

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    by_ecosystem: dict[str, int] = {}
    for component in sbom["components"]:
        ecosystem = component["purl"].split(":", 1)[1].split("/", 1)[0]
        by_ecosystem[ecosystem] = by_ecosystem.get(ecosystem, 0) + 1

    print(f"SBOM: {output}")
    print(f"  components: {len(sbom['components'])}")
    for ecosystem, count in sorted(by_ecosystem.items()):
        print(f"    {ecosystem}: {count}")
    print(f"  sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
