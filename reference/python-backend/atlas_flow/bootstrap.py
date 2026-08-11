"""Project Atlas bootstrap.

Detects the Project Atlas Framework version and validates compatibility on
open, per docs/03-implementation/PROJECT_ATLAS_INTEGRATION.md. Canonical
project truth stays in Git; this module only reads it.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel


class FrameworkInfo(BaseModel):
    name: str
    version: str
    entrypoint: str


def load_project_manifest(root: Path) -> dict[str, object]:
    manifest_path = root / "PROJECT_MANIFEST.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"PROJECT_MANIFEST.yaml not found under {root}")
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid PROJECT_MANIFEST.yaml at {manifest_path}")
    return data


def detect_framework(root: Path) -> FrameworkInfo:
    data = load_project_manifest(root)
    raw = data.get("framework")
    if not isinstance(raw, dict):
        raise ValueError("PROJECT_MANIFEST.yaml missing 'framework' section")
    return FrameworkInfo.model_validate(raw)
