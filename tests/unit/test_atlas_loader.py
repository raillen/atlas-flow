"""P01 Project Atlas loader tests against the real repository."""

import sys
import time
from pathlib import Path

import pytest
import yaml

from atlas_flow.goals import loader
from atlas_flow.goals.loader import (
    AtlasLoadError,
    resolve_project,
    validate_compatibility,
)
from atlas_flow.goals.models import ProjectAtlasContext

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

from fixtures.atlas_project import GoalSpec, ProjectSpec, write_project  # noqa: E402


def _project(root: Path, *goals: GoalSpec) -> Path:
    return write_project(
        root,
        ProjectSpec(
            project_id=root.name,
            name=root.name.title(),
            types=["library"],
            languages=["python"],
            goals=list(goals)
            or [GoalSpec(id="P00-G01", phase="P00", title="First", acceptance=["a"])],
        ),
    )


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


def test_validation_uses_resolved_project_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compatibility must be read from the opened project, not from cwd.

    Regression: validate_compatibility used to call detect_framework(Path.cwd()),
    so it validated whatever directory the process happened to run from. The
    backend/ package directory has no PROJECT_MANIFEST.yaml, which made this
    fail whenever the process was not started from the repository root.
    """
    monkeypatch.chdir(tmp_path)
    ctx = resolve_project(ROOT)

    assert ctx.root == ROOT
    validate_compatibility(ctx)


def test_atlas_load_error_on_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(AtlasLoadError, match="Manifest not found"):
        resolve_project(tmp_path)


def test_goals_have_phases(context: ProjectAtlasContext) -> None:
    for phase in context.phases:
        assert phase.id.startswith("P")
        for goal in phase.goals:
            assert goal.id.startswith(phase.id)
            assert goal.phase == phase.id


def test_reject_incompatible_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate incompatible version and verify actionable error."""
    from atlas_flow import bootstrap
    from atlas_flow.goals import loader

    def fake_detect(root: Path) -> bootstrap.FrameworkInfo:
        return bootstrap.FrameworkInfo(
            name="project-atlas-framework",
            version="9.9.9",
            entrypoint="ENTRYPOINT.md",
        )

    monkeypatch.setattr(loader, "detect_framework", fake_detect)
    ctx = resolve_project(ROOT)
    with pytest.raises(AtlasLoadError, match="Unsupported framework version 9.9.9"):
        validate_compatibility(ctx)


def test_missing_framework_manifest_raises_actionable_error(tmp_path: Path) -> None:
    """A project without PROJECT_MANIFEST.yaml reports the project path."""
    ctx = resolve_project(ROOT).model_copy(update={"root": tmp_path})
    with pytest.raises(AtlasLoadError, match="Cannot read framework version"):
        validate_compatibility(ctx)


class TestResolutionCache:
    """Re-parsing every Goal on every request is what made /api/goals slow."""

    def test_a_second_read_reuses_the_parsed_context(self, tmp_path: Path) -> None:
        root = _project(tmp_path / "cached")
        loader.forget_cached_projects()

        assert loader.resolve_project(root) is loader.resolve_project(root)

    def test_editing_a_goal_is_picked_up_immediately(self, tmp_path: Path) -> None:
        """Git is the authority; a cache that hides an edit would break that."""
        root = _project(tmp_path / "edited")
        loader.forget_cached_projects()
        assert loader.resolve_project(root).phases[0].goals[0].title == "First"

        goal_file = root / ".ai/goals/P00/P00-G01.yaml"
        data = yaml.safe_load(goal_file.read_text(encoding="utf-8"))
        data["title"] = "Renamed"
        goal_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        assert loader.resolve_project(root).phases[0].goals[0].title == "Renamed"

    def test_a_new_goal_file_invalidates_the_cache(self, tmp_path: Path) -> None:
        root = _project(tmp_path / "grown")
        loader.forget_cached_projects()
        assert len(loader.resolve_project(root).phases) == 1

        (root / ".ai/goals/P01").mkdir(parents=True)
        (root / ".ai/goals/P01/P01-G01.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "P01-G01",
                    "phase": "P01",
                    "title": "Second",
                    "state": "PLANNED",
                    "objective": "Do more",
                    "acceptance": ["b"],
                    "gates": {
                        "build": "required",
                        "tests": "required",
                        "review": "required",
                        "documentation": "required",
                    },
                    "evidence": [],
                    "history": [],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        assert len(loader.resolve_project(root).phases) == 2

    def test_the_cache_can_be_bypassed(self, tmp_path: Path) -> None:
        root = _project(tmp_path / "bypassed")
        loader.forget_cached_projects()

        first = loader.resolve_project(root)
        assert loader.resolve_project(root, use_cache=False) is not first

    def test_two_projects_do_not_share_a_cached_context(self, tmp_path: Path) -> None:
        one = _project(tmp_path / "one")
        two = _project(tmp_path / "two")
        loader.forget_cached_projects()

        assert loader.resolve_project(one).root != loader.resolve_project(two).root

    def test_the_cache_is_faster_than_parsing(self, tmp_path: Path) -> None:
        """The point of the cache, stated as a measurement rather than a hope."""
        root = _project(tmp_path / "measured")
        loader.forget_cached_projects()
        loader.resolve_project(root)

        started = time.perf_counter()
        for _ in range(50):
            loader.resolve_project(root)
        cached = time.perf_counter() - started

        started = time.perf_counter()
        for _ in range(50):
            loader.resolve_project(root, use_cache=False)
        parsed = time.perf_counter() - started

        assert cached < parsed / 2, f"cached {cached:.4f}s vs parsed {parsed:.4f}s"
