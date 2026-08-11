"""Configuration system with precedence chain (GAP-02)."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AtlasFlowConfig:
    """Merged configuration from precedence chain: env → user → project → defaults."""

    project_root: Path = Path.cwd()
    # Which project this runtime is serving. Read from PROJECT_MANIFEST.yaml,
    # never assumed: Atlas Flow is generic, and a hardcoded id would stamp this
    # repository's name on every event of somebody else's run.
    project_id: str = ""

    # Autonomy
    autonomy_mode: str = "agentic"
    planning_requires_human: bool = True

    # Concurrency
    max_parallel_tasks: int = 4
    max_retries_per_task: int = 3
    max_fallback_attempts: int = 2

    # Budget
    max_cost_per_run_usd: float = 10.0
    max_tokens_per_run: int = 1_000_000

    # Operational state. Canonical project truth stays in Git (ADR-009); this
    # directory only holds run/task/attempt state and the event log, and is
    # safe to delete at the cost of losing in-flight run history.
    state_dir: str = ".atlas-flow"
    database_file: str = "state.db"

    # Git
    worktree_base: str = ""
    isolate_mutating_tasks: bool = True
    worktree_strategy: str = "per-task"

    # Runners
    command_code_timeout_seconds: int = 600
    command_code_max_turns: int = 50
    # The ACP agent to launch, as an argv list. Empty means no ACP runner is
    # registered — there is no sensible default agent to guess at.
    acp_agent_command: list[str] = field(default_factory=list)

    # Provider credential references. Values are environment variable names or
    # keychain identifiers, never credential material.
    provider_credential_refs: dict[str, str] = field(default_factory=dict)

    # MCP
    mcp_enabled: bool = False
    mcp_servers: list[str] = field(default_factory=list)

    # Logging
    log_level: str = "INFO"
    # Redaction of agent output is unconditional; these patterns are added to
    # the built-in ones. It is not a switch, because a run that may leak a
    # token is not a configuration preference.
    redaction_patterns: list[str] = field(default_factory=list)

    # Retention
    artifact_retention_days: int = 30
    transcript_retention_days: int = 90

    def __post_init__(self) -> None:
        # Resolved here rather than only in load(), so a config built directly
        # still knows whose project it is.
        if not self.project_id:
            self.project_id = self._read_project_id(self.project_root)

    @property
    def state_path(self) -> Path:
        return self.project_root / self.state_dir

    @property
    def database_path(self) -> Path:
        return self.state_path / self.database_file

    @classmethod
    def load(cls, project_root: Path | None = None) -> AtlasFlowConfig:
        root = project_root or cls._find_root()
        config = cls(project_root=root)

        # Layer 1: defaults (already set in dataclass)

        # Layer 2: project config
        project_config = cls._load_project_config(root)
        config._apply_override(project_config)

        # Layer 3: user config (~/.atlas-flow.yaml)
        user_config = cls._load_user_config()
        config._apply_override(user_config)

        # Layer 4: environment variables
        config._apply_env_overrides()

        return config

    @staticmethod
    def _find_root() -> Path:
        here = Path.cwd()
        for parent in [here] + list(here.parents):
            if (parent / "PROJECT_MANIFEST.yaml").is_file():
                return parent
        return here

    @staticmethod
    def _read_project_id(root: Path) -> str:
        """The id the project declares, falling back to its directory name."""
        manifest = root / "PROJECT_MANIFEST.yaml"
        if manifest.is_file():
            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                project = data.get("project")
                if isinstance(project, dict) and project.get("id"):
                    return str(project["id"])
        return root.name or "unknown-project"

    @staticmethod
    def _load_project_config(root: Path) -> dict[str, object]:
        """Load project-level config from .ai/orchestration/ files."""
        merged: dict[str, object] = {}
        config_dir = root / ".ai" / "orchestration"
        if not config_dir.is_dir():
            return merged

        # autonomy-policy.yaml → autonomy_*
        autonomy_path = config_dir / "autonomy-policy.yaml"
        if autonomy_path.is_file():
            data = yaml.safe_load(autonomy_path.read_text())
            if isinstance(data, dict):
                pp = data.get("project_policy", {})
                if isinstance(pp, dict) and pp.get("current") is not None:
                    merged["autonomy_mode"] = pp["current"]

        # orchestrator.yaml → execution config
        orch_path = config_dir / "orchestrator.yaml"
        if orch_path.is_file():
            data = yaml.safe_load(orch_path.read_text())
            if isinstance(data, dict):
                exec_cfg = data.get("execution", {})
                if isinstance(exec_cfg, dict):
                    if "isolate_mutating_tasks" in exec_cfg:
                        merged["isolate_mutating_tasks"] = exec_cfg["isolate_mutating_tasks"]
                    if "worktree_strategy" in exec_cfg:
                        merged["worktree_strategy"] = exec_cfg["worktree_strategy"]

        # fallbacks.yaml → retry config. Only keys the file actually declares
        # are merged; anything absent must fall through to the dataclass
        # default rather than being looked up in this partial dict.
        fallback_path = config_dir / "fallbacks.yaml"
        if fallback_path.is_file():
            data = yaml.safe_load(fallback_path.read_text())
            if isinstance(data, dict):
                quality = data.get("quality", {})
                if isinstance(quality, dict) and "max_cross_model_attempts" in quality:
                    merged["max_retries_per_task"] = quality["max_cross_model_attempts"]

        # settings.yaml contains project-owned values that do not have a
        # canonical policy file of their own. It is intentionally flat so the
        # Settings UI can patch one key without rewriting unrelated policy.
        settings_path = config_dir / "settings.yaml"
        if settings_path.is_file():
            data = yaml.safe_load(settings_path.read_text())
            if isinstance(data, dict):
                known = {
                    "planning_requires_human",
                    "max_parallel_tasks",
                    "max_fallback_attempts",
                    "max_tokens_per_run",
                    "max_cost_per_run_usd",
                    "mcp_servers",
                }
                merged.update({key: data[key] for key in known if key in data})

        return merged

    @staticmethod
    def _load_user_config() -> dict[str, object]:
        user_path = Path.home() / ".atlas-flow.yaml"
        if user_path.is_file():
            data = yaml.safe_load(user_path.read_text())
            if isinstance(data, dict):
                return data
        return {}

    def _apply_override(self, overrides: dict[str, object]) -> None:
        for key, value in overrides.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def _apply_env_overrides(self) -> None:
        env_map = {
            "ATLAS_FLOW_MAX_PARALLEL": ("max_parallel_tasks", int),
            "ATLAS_FLOW_MAX_RETRIES": ("max_retries_per_task", int),
            "ATLAS_FLOW_LOG_LEVEL": ("log_level", str),
            "ATLAS_FLOW_AUTONOMY": ("autonomy_mode", str),
            "ATLAS_FLOW_STATE_DIR": ("state_dir", str),
        }
        for env_var, (attr, converter) in env_map.items():
            value = os.environ.get(env_var)
            if value is not None:
                setattr(self, attr, converter(value))

        agent = os.environ.get("ATLAS_FLOW_ACP_AGENT")
        if agent is not None:
            self.acp_agent_command = shlex.split(agent)
