from pathlib import Path

from atlas_flow.project.inspection import ProjectMode, inspect_project


def test_plain_directory_is_external(tmp_path: Path) -> None:
    result = inspect_project(tmp_path)

    assert result.mode == ProjectMode.EXTERNAL
    assert result.capabilities.can_explore
    assert result.capabilities.can_discuss
    assert result.capabilities.can_adapt
    assert not result.capabilities.can_plan
    assert not result.capabilities.can_run
    assert "PROJECT_MANIFEST.yaml" in result.missing_manifests


def test_project_with_unknown_framework_is_incompatible(tmp_path: Path) -> None:
    (tmp_path / "PROJECT_MANIFEST.yaml").write_text(
        "framework:\n  name: another-framework\n  version: 1.0.0\n",
        encoding="utf-8",
    )

    result = inspect_project(tmp_path)

    assert result.mode == ProjectMode.ATLAS_INCOMPATIBLE
    assert result.framework_name == "another-framework"
    assert not result.capabilities.can_adapt
    assert not result.capabilities.can_plan


def test_partial_atlas_project_recommends_adaptation(tmp_path: Path) -> None:
    (tmp_path / "PROJECT_MANIFEST.yaml").write_text(
        "framework:\n  name: project-atlas-framework\n  version: 0.1.0\n"
        "project:\n  id: sample\n",
        encoding="utf-8",
    )

    result = inspect_project(tmp_path)

    assert result.mode == ProjectMode.ATLAS_NEEDS_ADAPTATION
    assert result.framework_supported
    assert result.capabilities.can_adapt
    assert not result.capabilities.can_plan
    assert result.missing_manifests


def test_complete_atlas_fixture_is_ready(tmp_path: Path) -> None:
    from fixtures.atlas_project import CLI_TOOL, write_project

    write_project(tmp_path / "project", CLI_TOOL)
    result = inspect_project(tmp_path / "project")

    assert result.mode == ProjectMode.ATLAS_READY
    assert result.capabilities.can_plan
    assert result.capabilities.can_run
    assert result.capabilities.can_review
