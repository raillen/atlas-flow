"""P01 Project Atlas loader tests against the real repository."""

from pathlib import Path

import pytest

from atlas_flow.goals.loader import (
    AtlasLoadError,
    resolve_project,
    validate_compatibility,
)
from atlas_flow.goals.models import ProjectAtlasContext

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def context() -> ProjectAtlasContext:
    return resolve_project(ROOT)


def test_resolve_project_returns_all_components(context: ProjectAtlasContext) -> None:
    assert context.project.id == "atlas-flow"
    assert len(context.phases) >= 1


def test_agent_manifest_has_expected_roles(context: ProjectAtlasContext) -> None:
    assert "chief-architect" in context.agents.agents
    assert "goal-planner" in context.agents.agents
    assert "tester" in context.agents.agents


def test_skill_manifest_has_expected_skills(context: ProjectAtlasContext) -> None:
    assert "goal-contracts" in context.skills.skills
    assert "atlas-navigation" in context.skills.skills


def test_model_policy_has_primary_models(context: ProjectAtlasContext) -> None:
    primary = [r for r in context.model_policy.roster if r.priority == "primary"]
    assert len(primary) == 2
    keys = {r.key for r in primary}
    assert keys == {"deepseek-v4-pro", "mimo-v2.5-pro"}


def test_validation_passes_on_real_project() -> None:
    validate_compatibility(resolve_project(ROOT))


def test_atlas_load_error_on_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(AtlasLoadError, match="Manifest not found"):
        resolve_project(tmp_path)


def test_goals_have_phases(context: ProjectAtlasContext) -> None:
    for phase in context.phases:
        assert phase.id.startswith("P")
        for goal in phase.goals:
            assert goal.id.startswith(phase.id)
            assert goal.phase == phase.id


def test_reject_incompatible_bootstrap(tmp_path: Path, monkeypatch) -> None:
    """Simulate incompatible version and verify actionable error."""
    from atlas_flow import bootstrap

    def fake_detect(root: Path):
        return bootstrap.FrameworkInfo(
            name="project-atlas-framework",
            version="9.9.9",
            entrypoint="ENTRYPOINT.md",
        )

    monkeypatch.setattr(bootstrap, "detect_framework", fake_detect)
    ctx = resolve_project(ROOT)
    with pytest.raises(AtlasLoadError, match="Unsupported framework version 9.9.9"):
        validate_compatibility(ctx)
