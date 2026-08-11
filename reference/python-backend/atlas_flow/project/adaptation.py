"""Preview and apply a conservative Project Atlas scaffold."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from atlas_flow.project.inspection import ProjectInspection, ProjectMode


@dataclass(frozen=True)
class AdaptationFile:
    path: str
    action: str
    content: str
    reason: str


@dataclass(frozen=True)
class AdaptationPreview:
    ready: bool
    files: list[AdaptationFile]
    conflicts: list[str]
    limitations: list[str]


class AdaptationError(Exception):
    """Raised when an adaptation cannot be applied safely."""


def preview_adaptation(root: Path, inspection: ProjectInspection) -> AdaptationPreview:
    if inspection.mode == ProjectMode.ATLAS_INCOMPATIBLE:
        return AdaptationPreview(
            ready=False,
            files=[],
            conflicts=[],
            limitations=[
                "An incompatible framework requires a reviewed migration, not a scaffold."
            ],
        )

    files = _scaffold(inspection)
    conflicts = [item.path for item in files if (root / item.path).exists()]
    planned = [
        AdaptationFile(
            path=item.path,
            action="conflict" if item.path in conflicts else "create",
            content=item.content,
            reason=item.reason,
        )
        for item in files
    ]
    limitations = [
        "No Goal is generated or marked locked/done.",
        "No command from the project is executed during adaptation.",
        "Review generated files and commit them through Git after applying.",
    ]
    if not inspection.git_present:
        limitations.append("Execution remains unavailable until the project has a Git repository.")
    return AdaptationPreview(
        ready=any(item.action == "create" for item in planned),
        files=planned,
        conflicts=conflicts,
        limitations=limitations,
    )


def apply_adaptation(
    root: Path,
    inspection: ProjectInspection,
    accepted_paths: list[str],
) -> list[str]:
    preview = preview_adaptation(root, inspection)
    if inspection.mode == ProjectMode.ATLAS_INCOMPATIBLE:
        raise AdaptationError(
            "An incompatible framework requires a reviewed migration before applying."
        )

    planned = {item.path: item for item in preview.files}
    unknown = sorted(set(accepted_paths) - set(planned))
    if unknown:
        raise AdaptationError(
            f"Cannot apply paths not present in the preview: {', '.join(unknown)}"
        )

    written: list[str] = []
    for relative in accepted_paths:
        item = planned[relative]
        target = (root / relative).resolve()
        if target != root.resolve() and root.resolve() not in target.parents:
            raise AdaptationError(f"Adaptation path escapes project root: {relative}")
        if target.exists():
            raise AdaptationError(f"Refusing to overwrite existing file: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item.content, encoding="utf-8")
        written.append(relative)
    return written


def _scaffold(inspection: ProjectInspection) -> list[AdaptationFile]:
    project_id = _safe_id(inspection.project_id)
    project_name = inspection.project_name or project_id
    types = inspection.types or ["application"]
    type_yaml = yaml.safe_dump(types, default_flow_style=False, sort_keys=False).strip()

    files = {
        "PROJECT_MANIFEST.yaml": (
            "framework:\n"
            "  name: project-atlas-framework\n"
            "  version: 0.1.0\n"
            "  entrypoint: ENTRYPOINT.md\n"
            "project:\n"
            f"  id: {project_id}\n"
            f"  name: {project_name}\n"
            "  type:\n"
            f"{_indent(type_yaml, 4)}\n"
            "  status: in-development\n"
            "documentation:\n"
            "  atlas: docs/ATLAS.md\n"
            "  state: PROJECT_STATE.md\n"
        ),
        "ENTRYPOINT.md": (
            f"# {project_name}\n\n"
            "Project Atlas entrypoint. Review this scaffold before committing.\n"
        ),
        "PROJECT_STATE.md": (
            "# Project State\n\n"
            "Atlas Flow adaptation scaffold; status requires owner review.\n"
        ),
        "docs/ATLAS.md": "# Atlas\n\nAdd the canonical navigation for this project.\n",
        ".ai/context/project-profile.yaml": (
            "project:\n"
            f"  id: {project_id}\n"
            "  type:\n"
            f"{_indent(type_yaml, 4)}\n"
            "  languages: []\n"
            "  technologies: []\n"
            "  features: []\n"
            "  risk:\n"
            "    security: unknown\n"
        ),
        ".ai/goals/README.md": (
            "# Goals\n\nDefine Goals here after the project context and decisions are reviewed.\n"
        ),
        ".ai/agents/manifest.yaml": (
            "agents:\n  - goal-planner\n  - core-implementer\n  - reviewer\n"
            "selection_basis:\n  - project type\n  - risk\n"
        ),
        ".ai/skills/manifest.yaml": "skills:\n  - goal-contracts\n",
        ".ai/recipes/manifest.yaml": "recipes:\n  - implement-goal\n",
        ".ai/orchestration/model-policy.yaml": (
            "version: 1\n"
            "development_harness: command-code\n"
            "runtime_discovery:\n  command: cmd --list-models\n"
            "roster: []\n"
            "principles:\n  - runtime availability beats static assumptions\n"
        ),
        ".ai/orchestration/autonomy-policy.yaml": (
            "default: agentic\n"
            "modes:\n"
            "  controlled:\n    description: human approval at meaningful gates\n"
            "  agentic:\n    description: bounded execution with escalation\n"
            "project_policy:\n  current: agentic\n"
        ),
        ".ai/orchestration/orchestrator.yaml": (
            "development:\n  harness: command-code\n"
            "product:\n  runtime: atlas-flow\n"
            "protocols:\n  agent: acp\n  ui: ag-ui\n"
            "execution:\n  isolate_mutating_tasks: true\n  worktree_strategy: per-task\n"
        ),
        ".ai/orchestration/fallbacks.yaml": (
            "availability: route to the next reachable model\n"
            "quality:\n  max_cross_model_attempts: 2\n"
            "confidence:\n  escalate_below: 0.5\n"
            "human_escalation:\n  - unresolvable conflict\n"
        ),
    }
    return [
        AdaptationFile(
            path=path,
            action="create",
            content=content,
            reason="Required Project Atlas scaffold file.",
        )
        for path, content in files.items()
    ]


def _indent(value: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in value.splitlines())


def _safe_id(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in cleaned.split("-") if part) or "external-project"
