"""Typed, source-aware settings for Atlas Flow."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.mcp.registry import McpRegistry


class ConfigSource(StrEnum):
    DEFAULT = "default"
    PROJECT = "project"
    USER = "user"
    ENVIRONMENT = "environment"


class ConfigScope(StrEnum):
    USER = "user"
    PROJECT = "project"


@dataclass(frozen=True)
class SettingSpec:
    key: str
    default: object
    scope: ConfigScope
    restart_required: bool
    applies_to: str
    description: str
    kind: str = "text"


SETTING_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        "autonomy_mode",
        "agentic",
        ConfigScope.PROJECT,
        True,
        "new plans and runs",
        "Default autonomy policy.",
        "select",
    ),
    SettingSpec(
        "planning_requires_human",
        True,
        ConfigScope.PROJECT,
        False,
        "new plans",
        "Require approval before a plan is locked.",
        "boolean",
    ),
    SettingSpec(
        "max_parallel_tasks",
        4,
        ConfigScope.PROJECT,
        False,
        "new runs",
        "Maximum concurrent tasks.",
        "integer",
    ),
    SettingSpec(
        "max_retries_per_task",
        3,
        ConfigScope.PROJECT,
        False,
        "new plans and runs",
        "Retries allowed for each task.",
        "integer",
    ),
    SettingSpec(
        "max_fallback_attempts",
        2,
        ConfigScope.PROJECT,
        False,
        "new runs",
        "Fallback models allowed for a failed task.",
        "integer",
    ),
    SettingSpec(
        "max_tokens_per_run",
        1_000_000,
        ConfigScope.PROJECT,
        False,
        "new runs",
        "Reported token ceiling; zero disables this dimension.",
        "integer",
    ),
    SettingSpec(
        "max_cost_per_run_usd",
        10.0,
        ConfigScope.PROJECT,
        False,
        "new runs",
        "Reported cost ceiling; zero disables this dimension.",
        "number",
    ),
    SettingSpec(
        "isolate_mutating_tasks",
        True,
        ConfigScope.PROJECT,
        True,
        "new runs",
        "Use isolated worktrees for mutating tasks.",
        "boolean",
    ),
    SettingSpec(
        "worktree_strategy",
        "per-task",
        ConfigScope.PROJECT,
        True,
        "new runs",
        "How mutating tasks receive worktrees.",
        "select",
    ),
    SettingSpec(
        "command_code_timeout_seconds",
        600,
        ConfigScope.USER,
        False,
        "new runs",
        "Command Code timeout.",
        "integer",
    ),
    SettingSpec(
        "command_code_max_turns",
        50,
        ConfigScope.USER,
        False,
        "new runs",
        "Maximum Command Code turns.",
        "integer",
    ),
    SettingSpec(
        "mcp_enabled",
        False,
        ConfigScope.PROJECT,
        True,
        "new runs",
        "Forward declared MCP servers to agents.",
        "boolean",
    ),
    SettingSpec(
        "mcp_servers",
        [],
        ConfigScope.PROJECT,
        True,
        "new runs",
        "Optional MCP server allowlist.",
        "list",
    ),
    SettingSpec(
        "log_level",
        "INFO",
        ConfigScope.USER,
        True,
        "backend restart",
        "Backend log level.",
        "select",
    ),
    SettingSpec(
        "artifact_retention_days",
        30,
        ConfigScope.USER,
        False,
        "future cleanup",
        "Retention for generated artifacts.",
        "integer",
    ),
    SettingSpec(
        "transcript_retention_days",
        90,
        ConfigScope.USER,
        False,
        "future cleanup",
        "Retention for transcripts.",
        "integer",
    ),
)

ENVIRONMENT_FIELDS = {
    "max_parallel_tasks": "ATLAS_FLOW_MAX_PARALLEL",
    "max_retries_per_task": "ATLAS_FLOW_MAX_RETRIES",
    "log_level": "ATLAS_FLOW_LOG_LEVEL",
    "autonomy_mode": "ATLAS_FLOW_AUTONOMY",
    "state_dir": "ATLAS_FLOW_STATE_DIR",
}

PROJECT_FILES = {
    "autonomy_mode": (".ai/orchestration/autonomy-policy.yaml", "project_policy", "current"),
    "isolate_mutating_tasks": (
        ".ai/orchestration/orchestrator.yaml",
        "execution",
        "isolate_mutating_tasks",
    ),
    "worktree_strategy": (
        ".ai/orchestration/orchestrator.yaml",
        "execution",
        "worktree_strategy",
    ),
    "max_retries_per_task": (
        ".ai/orchestration/fallbacks.yaml",
        "quality",
        "max_cross_model_attempts",
    ),
    "mcp_enabled": (".ai/orchestration/mcp-servers.yaml", None, "enabled"),
    # settings.yaml is intentionally flat: config.py reads each of these keys
    # directly, so the Settings UI can patch one key without rewriting other
    # policy. mcp_servers lives here too, next to its enable switch.
    "planning_requires_human": (
        ".ai/orchestration/settings.yaml",
        None,
        "planning_requires_human",
    ),
    "max_parallel_tasks": (
        ".ai/orchestration/settings.yaml",
        None,
        "max_parallel_tasks",
    ),
    "max_fallback_attempts": (
        ".ai/orchestration/settings.yaml",
        None,
        "max_fallback_attempts",
    ),
    "max_tokens_per_run": (
        ".ai/orchestration/settings.yaml",
        None,
        "max_tokens_per_run",
    ),
    "max_cost_per_run_usd": (
        ".ai/orchestration/settings.yaml",
        None,
        "max_cost_per_run_usd",
    ),
    "mcp_servers": (".ai/orchestration/settings.yaml", None, "mcp_servers"),
}

USER_KEYS = {spec.key for spec in SETTING_SPECS if spec.scope == ConfigScope.USER}
PROJECT_KEYS = {spec.key for spec in SETTING_SPECS if spec.scope == ConfigScope.PROJECT}


@dataclass(frozen=True)
class SettingView:
    key: str
    value: object
    default: object
    source: ConfigSource
    scope: ConfigScope
    restart_required: bool
    applies_to: str
    description: str
    kind: str
    environment_variable: str | None = None


class SettingsError(Exception):
    """Raised for invalid or unsafe settings changes."""


def load_settings(root: Path) -> dict[str, SettingView]:
    config = AtlasFlowConfig.load(root)
    user = _read_yaml(Path.home() / ".atlas-flow.yaml")
    project = _read_project_overrides(root)
    values: dict[str, SettingView] = {}

    for spec in SETTING_SPECS:
        value = getattr(config, spec.key)
        source = ConfigSource.DEFAULT
        if spec.key in project:
            value, source = project[spec.key]
        if spec.key in user:
            value, source = user[spec.key], ConfigSource.USER
        if spec.key in ENVIRONMENT_FIELDS and ENVIRONMENT_FIELDS[spec.key] in os.environ:
            value = _convert(os.environ[ENVIRONMENT_FIELDS[spec.key]], spec.kind)
            source = ConfigSource.ENVIRONMENT
        values[spec.key] = SettingView(
            key=spec.key,
            value=value,
            default=spec.default,
            source=source,
            scope=spec.scope,
            restart_required=spec.restart_required,
            applies_to=spec.applies_to,
            description=spec.description,
            kind=spec.kind,
            environment_variable=ENVIRONMENT_FIELDS.get(spec.key),
        )
    return values


def apply_settings(
    root: Path, patch: dict[str, object], scope: ConfigScope
) -> dict[str, SettingView]:
    current = load_settings(root)
    if not patch:
        return current
    allowed = USER_KEYS if scope == ConfigScope.USER else PROJECT_KEYS
    invalid = sorted(set(patch) - allowed)
    if invalid:
        raise SettingsError(f"Settings cannot be written in {scope}: {', '.join(invalid)}")

    for key, value in patch.items():
        view = current[key]
        if view.source == ConfigSource.ENVIRONMENT:
            raise SettingsError(
                f"{key} is controlled by {view.environment_variable}; "
                "change that environment variable instead"
            )
        _validate_value(view.kind, key, value)

    if scope == ConfigScope.USER:
        path = Path.home() / ".atlas-flow.yaml"
        data = _read_yaml(path)
        data.update(patch)
        _atomic_yaml_write(path, data)
    else:
        _apply_project_patch(root, patch)
    return load_settings(root)


def reset_settings(root: Path, keys: list[str], scope: ConfigScope) -> dict[str, SettingView]:
    allowed = USER_KEYS if scope == ConfigScope.USER else PROJECT_KEYS
    invalid = sorted(set(keys) - allowed)
    if invalid:
        raise SettingsError(f"Settings cannot be reset in {scope}: {', '.join(invalid)}")
    if scope == ConfigScope.USER:
        path = Path.home() / ".atlas-flow.yaml"
        data = _read_yaml(path)
        for key in keys:
            data.pop(key, None)
        _atomic_yaml_write(path, data)
    else:
        for key in keys:
            _remove_project_override(root, key)
    return load_settings(root)


def inspect_mcp(root: Path, config: AtlasFlowConfig) -> dict[str, object]:
    registry = McpRegistry.load(config)
    return {
        "enabled": registry.enabled,
        "servers": [
            {
                "name": server.name,
                "command": server.command,
                "args": server.args,
                "readOnly": server.read_only,
                "roles": server.roles,
            }
            for server in registry.servers
        ],
        "skipped": dict(registry.skipped),
    }


def _read_project_overrides(root: Path) -> dict[str, tuple[object, ConfigSource]]:
    result: dict[str, tuple[object, ConfigSource]] = {}
    for key, (relative, section, field) in PROJECT_FILES.items():
        data = _read_yaml(root / relative)
        value: object = data
        if section is not None:
            value = data.get(section, {}) if isinstance(data, dict) else {}
        if isinstance(value, dict) and field in value:
            result[key] = (value[field], ConfigSource.PROJECT)
    return result


def _apply_project_patch(root: Path, patch: dict[str, object]) -> None:
    grouped: dict[Path, dict[str, object]] = {}
    for key, value in patch.items():
        relative, section, field = PROJECT_FILES[key]
        path = root / relative
        data = grouped.setdefault(path, _read_yaml(path))
        target = data if section is None else data.setdefault(section, {})
        if not isinstance(target, dict):
            raise SettingsError(f"Cannot update malformed settings file: {relative}")
        target[field] = value
    for path, data in grouped.items():
        _atomic_yaml_write(path, data)


def _remove_project_override(root: Path, key: str) -> None:
    relative, section, field = PROJECT_FILES[key]
    path = root / relative
    data = _read_yaml(path)
    target = data if section is None else data.get(section, {})
    if isinstance(target, dict):
        target.pop(field, None)
    _atomic_yaml_write(path, data)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SettingsError(f"Could not read settings file {path}: {exc}") from exc
    return value if isinstance(value, dict) else {}


def _atomic_yaml_write(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)
    except OSError as exc:
        raise SettingsError(f"Could not write settings file {path}: {exc}") from exc


def _convert(value: str, kind: str) -> object:
    if kind == "boolean":
        return value.lower() in {"1", "true", "yes", "on"}
    if kind == "integer":
        return int(value)
    if kind == "number":
        return float(value)
    return value


def _validate_value(kind: str, key: str, value: object) -> None:
    if kind == "boolean" and not isinstance(value, bool):
        raise SettingsError(f"{key} must be boolean")
    if kind == "integer" and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
        raise SettingsError(f"{key} must be a non-negative integer")
    if kind == "number" and (
        not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
    ):
        raise SettingsError(f"{key} must be a non-negative number")
    if kind == "list" and not isinstance(value, list):
        raise SettingsError(f"{key} must be a list")
    if kind in {"text", "select"} and not isinstance(value, str):
        raise SettingsError(f"{key} must be text")
