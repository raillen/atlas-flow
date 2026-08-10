"""Project Atlas loader — validates and resolves the project context (P01)."""

from __future__ import annotations

from pathlib import Path

import yaml

from atlas_flow.bootstrap import detect_framework
from atlas_flow.goals.models import (
    AgentManifest,
    AutonomyPolicy,
    FallbackConfig,
    Goal,
    ModelPolicy,
    OrchestratorConfig,
    Phase,
    ProjectAtlasContext,
    ProjectProfile,
    RecipeManifest,
    SkillManifest,
)


class AtlasLoadError(Exception):
    """Actionable error for incompatible or invalid manifests."""


def _yaml_load(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise AtlasLoadError(f"Manifest not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AtlasLoadError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AtlasLoadError(f"Expected mapping in {path}, got {type(data).__name__}")
    return data


def load_project_profile(root: Path) -> ProjectProfile:
    raw = _yaml_load(root / ".ai/context/project-profile.yaml")
    return ProjectProfile.model_validate(raw["project"])


def load_goals(root: Path) -> list[Phase]:
    goals_root = root / ".ai/goals"
    if not goals_root.is_dir():
        raise AtlasLoadError(f"Goals directory not found: {goals_root}")
    phases: dict[str, Phase] = {}
    for goal_file in sorted(goals_root.rglob("*.yaml")):
        raw = _yaml_load(goal_file)
        goal = Goal.model_validate(raw)
        phase = phases.setdefault(goal.phase, Phase(id=goal.phase))
        phase.goals.append(goal)
    return sorted(phases.values(), key=lambda p: p.id)


def load_agent_manifest(root: Path) -> AgentManifest:
    raw = _yaml_load(root / ".ai/agents/manifest.yaml")
    return AgentManifest.model_validate(raw)


def load_skill_manifest(root: Path) -> SkillManifest:
    raw = _yaml_load(root / ".ai/skills/manifest.yaml")
    return SkillManifest.model_validate(raw)


def load_recipe_manifest(root: Path) -> RecipeManifest:
    raw = _yaml_load(root / ".ai/recipes/manifest.yaml")
    return RecipeManifest.model_validate(raw)


def load_model_policy(root: Path) -> ModelPolicy:
    raw = _yaml_load(root / ".ai/orchestration/model-policy.yaml")
    return ModelPolicy.model_validate(raw)


def load_autonomy_policy(root: Path) -> AutonomyPolicy:
    raw = _yaml_load(root / ".ai/orchestration/autonomy-policy.yaml")
    return AutonomyPolicy.model_validate(raw)


def load_orchestrator(root: Path) -> OrchestratorConfig:
    raw = _yaml_load(root / ".ai/orchestration/orchestrator.yaml")
    return OrchestratorConfig.model_validate(raw)


def load_fallbacks(root: Path) -> FallbackConfig:
    raw = _yaml_load(root / ".ai/orchestration/fallbacks.yaml")
    return FallbackConfig.model_validate(raw)


def resolve_project(root: Path) -> ProjectAtlasContext:
    """Load and validate all Project Atlas manifests.

    Raises AtlasLoadError with actionable message on incompatible/invalid
    manifests. No forked Goal semantics are introduced — this reads canonical
    Project Atlas format exactly.
    """
    return ProjectAtlasContext(
        root=root,
        project=load_project_profile(root),
        phases=load_goals(root),
        agents=load_agent_manifest(root),
        skills=load_skill_manifest(root),
        recipes=load_recipe_manifest(root),
        model_policy=load_model_policy(root),
        autonomy_policy=load_autonomy_policy(root),
        orchestrator=load_orchestrator(root),
        fallbacks=load_fallbacks(root),
    )


def validate_compatibility(ctx: ProjectAtlasContext) -> None:
    """Detect incompatible Project Atlas version before proceeding.

    The framework version is read from the PROJECT_MANIFEST.yaml of the
    resolved project — never from the process working directory, which is
    unrelated to which project was opened. Currently we only accept 0.1.x of
    project-atlas-framework.
    """
    try:
        fw = detect_framework(ctx.root)
    except (FileNotFoundError, ValueError) as exc:
        raise AtlasLoadError(
            f"Cannot read framework version for project at {ctx.root}: {exc}"
        ) from exc

    if fw.name != "project-atlas-framework":
        raise AtlasLoadError(f"Expected project-atlas-framework, got {fw.name}")
    major, minor, *_ = fw.version.split(".")
    if (int(major), int(minor)) != (0, 1):
        raise AtlasLoadError(
            f"Unsupported framework version {fw.version}. Currently supported: 0.1.x"
        )
