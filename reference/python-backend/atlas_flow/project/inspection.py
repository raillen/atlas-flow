"""Non-destructive project inspection before Atlas execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from atlas_flow.goals.loader import AtlasLoadError, resolve_project


class ProjectMode(StrEnum):
    ATLAS_READY = "atlas-ready"
    ATLAS_NEEDS_ADAPTATION = "atlas-needs-adaptation"
    ATLAS_INCOMPATIBLE = "atlas-incompatible"
    EXTERNAL = "external"


REQUIRED_DIRECTORIES = (".ai/goals",)

REQUIRED_MANIFESTS = (
    "PROJECT_MANIFEST.yaml",
    "ENTRYPOINT.md",
    "PROJECT_STATE.md",
    "docs/ATLAS.md",
    ".ai/context/project-profile.yaml",
    ".ai/agents/manifest.yaml",
    ".ai/skills/manifest.yaml",
    ".ai/recipes/manifest.yaml",
    ".ai/orchestration/model-policy.yaml",
    ".ai/orchestration/autonomy-policy.yaml",
    ".ai/orchestration/orchestrator.yaml",
    ".ai/orchestration/fallbacks.yaml",
)


@dataclass(frozen=True)
class ProjectCapabilities:
    can_explore: bool
    can_discuss: bool
    can_adapt: bool
    can_plan: bool
    can_run: bool
    can_review: bool


@dataclass(frozen=True)
class ProjectInspection:
    root: Path
    mode: ProjectMode
    project_id: str
    project_name: str
    types: list[str]
    framework_name: str | None
    framework_version: str | None
    framework_supported: bool
    git_present: bool
    missing_manifests: list[str]
    invalid_manifests: list[str]
    reason: str
    recommendation: str
    capabilities: ProjectCapabilities


def inspect_project(root: Path) -> ProjectInspection:
    """Classify a directory without running project code or shell commands."""
    root = root.resolve()
    manifest = root / "PROJECT_MANIFEST.yaml"
    git_present = (root / ".git").exists()

    if not manifest.is_file():
        return _inspection(
            root=root,
            mode=ProjectMode.EXTERNAL,
            project_id=root.name or "external-project",
            project_name=root.name or str(root),
            types=_detected_types(root),
            framework_name=None,
            framework_version=None,
            framework_supported=False,
            git_present=git_present,
            missing_manifests=list(REQUIRED_MANIFESTS),
            invalid_manifests=[],
            reason="This directory does not declare Project Atlas manifests.",
            recommendation="Inspect the project, then preview an adaptation to Project Atlas.",
        )

    raw, manifest_error = _read_mapping(manifest)
    if manifest_error is not None:
        return _inspection(
            root=root,
            mode=ProjectMode.ATLAS_NEEDS_ADAPTATION,
            project_id=root.name or "unknown-project",
            project_name=root.name or str(root),
            types=_detected_types(root),
            framework_name=None,
            framework_version=None,
            framework_supported=False,
            git_present=git_present,
            missing_manifests=[],
            invalid_manifests=["PROJECT_MANIFEST.yaml"],
            reason=manifest_error,
            recommendation=(
                "Repair or replace the invalid Project Atlas manifest "
                "after reviewing a preview."
            ),
        )

    framework = raw.get("framework")
    framework_name: str | None = None
    framework_version: str | None = None
    project = raw.get("project")
    project_id = root.name or "unknown-project"
    project_name = project_id
    types: list[str] = _detected_types(root)
    if isinstance(project, dict):
        project_id = str(project.get("id") or project_id)
        project_name = str(project.get("name") or project_id)
        types = _strings(project.get("type")) or types
    if isinstance(framework, dict):
        framework_name = _optional_string(framework.get("name"))
        framework_version = _optional_string(framework.get("version"))

    if framework_name != "project-atlas-framework":
        return _inspection(
            root=root,
            mode=ProjectMode.ATLAS_INCOMPATIBLE,
            project_id=project_id,
            project_name=project_name,
            types=types,
            framework_name=framework_name,
            framework_version=framework_version,
            framework_supported=False,
            git_present=git_present,
            missing_manifests=[],
            invalid_manifests=["PROJECT_MANIFEST.yaml"],
            reason=(
                f"This project declares {framework_name or 'no framework'}, "
                "not project-atlas-framework."
            ),
            recommendation=(
                "Review the compatibility report and adapt deliberately; "
                "automatic conversion is disabled."
            ),
        )

    if not _supported_version(framework_version):
        return _inspection(
            root=root,
            mode=ProjectMode.ATLAS_INCOMPATIBLE,
            project_id=project_id,
            project_name=project_name,
            types=types,
            framework_name=framework_name,
            framework_version=framework_version,
            framework_supported=False,
            git_present=git_present,
            missing_manifests=[],
            invalid_manifests=["PROJECT_MANIFEST.yaml"],
            reason=(
                f"Framework version {framework_version or 'unknown'} is not supported; "
                "Atlas Flow currently supports 0.1.x."
            ),
            recommendation="Inspect and review an explicit framework migration before execution.",
        )

    missing = [relative for relative in REQUIRED_MANIFESTS if not (root / relative).is_file()]
    missing.extend(relative for relative in REQUIRED_DIRECTORIES if not (root / relative).is_dir())
    invalid = [
        relative
        for relative in REQUIRED_MANIFESTS
        if relative not in missing and _invalid_file(root / relative)
    ]
    if not missing and not invalid:
        try:
            context = resolve_project(root)
            project_id = context.project.id
            types = context.project.types
            project_name = project_id
        except (AtlasLoadError, ValueError, TypeError, KeyError) as exc:
            invalid = ["Project Atlas manifests"]
            reason = f"Project Atlas manifests are not valid: {exc}"
        else:
            return _inspection(
                root=root,
                mode=ProjectMode.ATLAS_READY,
                project_id=project_id,
                project_name=project_name,
                types=types,
                framework_name=framework_name,
                framework_version=framework_version,
                framework_supported=True,
                git_present=git_present,
                missing_manifests=[],
                invalid_manifests=[],
                reason=(
                    "Project Atlas manifests are valid and the supported framework "
                    "is available."
                ),
                recommendation="Project is ready for Goal planning and execution.",
            )
    else:
        reason = "Project Atlas is declared but required manifests need attention."

    return _inspection(
        root=root,
        mode=ProjectMode.ATLAS_NEEDS_ADAPTATION,
        project_id=project_id,
        project_name=project_name,
        types=types,
        framework_name=framework_name,
        framework_version=framework_version,
        framework_supported=True,
        git_present=git_present,
        missing_manifests=missing,
        invalid_manifests=invalid,
        reason=reason,
        recommendation=(
            "Review the missing or invalid manifests, then preview an authorized "
            "adaptation."
        ),
    )


def _inspection(
    *,
    root: Path,
    mode: ProjectMode,
    project_id: str,
    project_name: str,
    types: list[str],
    framework_name: str | None,
    framework_version: str | None,
    framework_supported: bool,
    git_present: bool,
    missing_manifests: list[str],
    invalid_manifests: list[str],
    reason: str,
    recommendation: str,
) -> ProjectInspection:
    ready = mode == ProjectMode.ATLAS_READY
    capabilities = ProjectCapabilities(
        can_explore=True,
        can_discuss=True,
        can_adapt=mode in {
            ProjectMode.EXTERNAL,
            ProjectMode.ATLAS_NEEDS_ADAPTATION,
        },
        can_plan=ready,
        can_run=ready and git_present,
        can_review=ready,
    )
    if ready and not git_present:
        reason = "Project Atlas manifests are valid, but Git is required for isolated execution."
        recommendation = "Initialize or open a Git repository before running a Goal."
    return ProjectInspection(
        root=root,
        mode=mode,
        project_id=project_id,
        project_name=project_name,
        types=types,
        framework_name=framework_name,
        framework_version=framework_version,
        framework_supported=framework_supported,
        git_present=git_present,
        missing_manifests=missing_manifests,
        invalid_manifests=invalid_manifests,
        reason=reason,
        recommendation=recommendation,
        capabilities=capabilities,
    )


def _read_mapping(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return {}, f"Could not read {path.name}: {exc}"
    if not isinstance(value, dict):
        return {}, f"{path.name} must contain a mapping."
    return value, None


def _invalid_file(path: Path) -> bool:
    if path.suffix not in {".yaml", ".yml"}:
        try:
            return not path.read_text(encoding="utf-8").strip()
        except OSError:
            return True
    _, error = _read_mapping(path)
    return error is not None


def _supported_version(version: str | None) -> bool:
    if version is None:
        return False
    parts = version.split(".")
    try:
        return len(parts) >= 2 and (int(parts[0]), int(parts[1])) == (0, 1)
    except ValueError:
        return False


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None and str(value).strip() else None


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _detected_types(root: Path) -> list[str]:
    signals = {
        "pyproject.toml": "python",
        "package.json": "javascript/typescript",
        "Cargo.toml": "rust",
        "go.mod": "go",
        "pom.xml": "java",
        "composer.json": "php",
    }
    return [kind for filename, kind in signals.items() if (root / filename).is_file()]
