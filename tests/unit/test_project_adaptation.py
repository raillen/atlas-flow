from pathlib import Path

import pytest

from atlas_flow.project.adaptation import AdaptationError, apply_adaptation, preview_adaptation
from atlas_flow.project.inspection import ProjectMode, inspect_project


def test_preview_does_not_write_or_create_goals(tmp_path: Path) -> None:
    inspection = inspect_project(tmp_path)
    preview = preview_adaptation(tmp_path, inspection)

    assert preview.ready
    assert not (tmp_path / "PROJECT_MANIFEST.yaml").exists()
    assert not (tmp_path / ".ai/goals").exists()
    assert all(item.action == "create" for item in preview.files)


def test_apply_only_creates_selected_preview_files(tmp_path: Path) -> None:
    inspection = inspect_project(tmp_path)
    preview = preview_adaptation(tmp_path, inspection)
    selected = [preview.files[0].path]

    written = apply_adaptation(tmp_path, inspection, selected)

    assert written == selected
    assert (tmp_path / selected[0]).is_file()
    assert not (tmp_path / ".ai/goals").exists()


def test_apply_refuses_overwrite_and_unknown_paths(tmp_path: Path) -> None:
    inspection = inspect_project(tmp_path)
    preview = preview_adaptation(tmp_path, inspection)
    selected = [preview.files[0].path]
    apply_adaptation(tmp_path, inspection, selected)

    with pytest.raises(AdaptationError, match="overwrite"):
        apply_adaptation(tmp_path, inspection, selected)
    with pytest.raises(AdaptationError, match="not present"):
        apply_adaptation(tmp_path, inspection, ["unknown.yaml"])


def test_incompatible_framework_cannot_use_scaffold(tmp_path: Path) -> None:
    (tmp_path / "PROJECT_MANIFEST.yaml").write_text(
        "framework:\n  name: other\n  version: 1.0.0\n", encoding="utf-8"
    )
    inspection = inspect_project(tmp_path)

    assert inspection.mode == ProjectMode.ATLAS_INCOMPATIBLE
    with pytest.raises(AdaptationError, match="incompatible"):
        apply_adaptation(tmp_path, inspection, [])
