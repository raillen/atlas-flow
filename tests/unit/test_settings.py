"""Settings layering, validation and persistence."""

from pathlib import Path

import pytest

from atlas_flow.settings import (
    ConfigScope,
    ConfigSource,
    SettingsError,
    apply_settings,
    load_settings,
    reset_settings,
)


@pytest.fixture
def user_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect Path.home() so user-scope writes never touch the real one."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def test_defaults_are_reported_with_source_default(tmp_path: Path) -> None:
    views = load_settings(tmp_path)

    assert views["max_parallel_tasks"].value == 4
    assert views["max_parallel_tasks"].source == ConfigSource.DEFAULT
    assert views["log_level"].value == "INFO"


def test_project_override_wins_over_default_and_serializes_value_only(
    tmp_path: Path,
) -> None:
    policy = tmp_path / ".ai" / "orchestration" / "autonomy-policy.yaml"
    policy.parent.mkdir(parents=True)
    policy.write_text("project_policy:\n  current: supervised\n", encoding="utf-8")

    views = load_settings(tmp_path)

    assert views["autonomy_mode"].value == "supervised"
    assert views["autonomy_mode"].source == ConfigSource.PROJECT
    # The value must be the scalar, not a (value, source) tuple leaking through.
    assert isinstance(views["autonomy_mode"].value, str)


def test_user_override_wins_over_project(tmp_path: Path, user_home: Path) -> None:
    (user_home / ".atlas-flow.yaml").write_text(
        "max_parallel_tasks: 8\n", encoding="utf-8"
    )
    orchestrator = tmp_path / ".ai" / "orchestration" / "orchestrator.yaml"
    orchestrator.parent.mkdir(parents=True)
    orchestrator.write_text(
        "execution:\n  worktree_strategy: per-task\n", encoding="utf-8"
    )

    views = load_settings(tmp_path)

    assert views["max_parallel_tasks"].value == 8
    assert views["max_parallel_tasks"].source == ConfigSource.USER


def test_environment_overrides_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FLOW_MAX_PARALLEL", "12")

    views = load_settings(tmp_path)

    assert views["max_parallel_tasks"].value == 12
    assert views["max_parallel_tasks"].source == ConfigSource.ENVIRONMENT
    assert views["max_parallel_tasks"].environment_variable == "ATLAS_FLOW_MAX_PARALLEL"


def test_user_apply_writes_home_yaml(tmp_path: Path, user_home: Path) -> None:
    apply_settings(tmp_path, {"log_level": "DEBUG"}, ConfigScope.USER)

    written = (user_home / ".atlas-flow.yaml").read_text(encoding="utf-8")
    assert "DEBUG" in written
    views = load_settings(tmp_path)
    assert views["log_level"].value == "DEBUG"
    assert views["log_level"].source == ConfigSource.USER


def test_user_reset_removes_override(tmp_path: Path, user_home: Path) -> None:
    apply_settings(tmp_path, {"log_level": "DEBUG"}, ConfigScope.USER)
    assert load_settings(tmp_path)["log_level"].value == "DEBUG"

    reset_settings(tmp_path, ["log_level"], ConfigScope.USER)

    assert load_settings(tmp_path)["log_level"].value == "INFO"


def test_project_apply_writes_orchestration_yaml(tmp_path: Path) -> None:
    apply_settings(tmp_path, {"max_retries_per_task": 5}, ConfigScope.PROJECT)

    written = (tmp_path / ".ai" / "orchestration" / "fallbacks.yaml").read_text(
        encoding="utf-8"
    )
    assert "max_cross_model_attempts: 5" in written
    assert load_settings(tmp_path)["max_retries_per_task"].value == 5


def test_project_reset_removes_specific_override(tmp_path: Path) -> None:
    apply_settings(tmp_path, {"max_retries_per_task": 5}, ConfigScope.PROJECT)
    apply_settings(tmp_path, {"worktree_strategy": "single"}, ConfigScope.PROJECT)

    reset_settings(tmp_path, ["max_retries_per_task"], ConfigScope.PROJECT)

    views = load_settings(tmp_path)
    assert views["max_retries_per_task"].value == 3  # back to default
    assert views["worktree_strategy"].value == "single"  # untouched


def test_project_apply_writes_flat_settings_yaml_for_every_flat_key(
    tmp_path: Path,
) -> None:
    # Regression: the flat keys of .ai/orchestration/settings.yaml were missing
    # from PROJECT_FILES, so patching any of them raised KeyError (HTTP 500).
    patch = {
        "planning_requires_human": False,
        "max_parallel_tasks": 6,
        "max_fallback_attempts": 1,
        "max_tokens_per_run": 500_000,
        "max_cost_per_run_usd": 25.0,
        "mcp_servers": ["stdio"],
    }

    apply_settings(tmp_path, patch, ConfigScope.PROJECT)

    written = (tmp_path / ".ai" / "orchestration" / "settings.yaml").read_text(
        encoding="utf-8"
    )
    for key in patch:
        assert f"{key}:" in written, f"{key} missing from settings.yaml"
    views = load_settings(tmp_path)
    for key, value in patch.items():
        assert views[key].value == value, key
        assert views[key].source == ConfigSource.PROJECT, key


def test_project_reset_flat_key_returns_to_default(tmp_path: Path) -> None:
    apply_settings(tmp_path, {"max_parallel_tasks": 6}, ConfigScope.PROJECT)
    assert load_settings(tmp_path)["max_parallel_tasks"].value == 6

    reset_settings(tmp_path, ["max_parallel_tasks"], ConfigScope.PROJECT)

    assert load_settings(tmp_path)["max_parallel_tasks"].value == 4


def test_scope_rejects_foreign_keys(tmp_path: Path, user_home: Path) -> None:
    with pytest.raises(SettingsError, match="cannot be written in user"):
        apply_settings(tmp_path, {"max_parallel_tasks": 8}, ConfigScope.USER)

    with pytest.raises(SettingsError, match="cannot be written in project"):
        apply_settings(tmp_path, {"log_level": "DEBUG"}, ConfigScope.PROJECT)


def test_environment_controlled_key_cannot_be_written(
    tmp_path: Path, user_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_FLOW_MAX_PARALLEL", "12")

    with pytest.raises(SettingsError, match="controlled by ATLAS_FLOW_MAX_PARALLEL"):
        apply_settings(tmp_path, {"max_parallel_tasks": 8}, ConfigScope.PROJECT)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("max_parallel_tasks", -1),
        ("max_parallel_tasks", True),
        ("max_cost_per_run_usd", "ten"),
        ("planning_requires_human", "yes"),
        ("mcp_servers", "not-a-list"),
        ("log_level", 3),
    ],
)
def test_type_validation_rejects_bad_values(
    tmp_path: Path, user_home: Path, key: str, value: object
) -> None:
    with pytest.raises(SettingsError):
        apply_settings(tmp_path, {key: value}, ConfigScope.PROJECT)
