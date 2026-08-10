"""Configuration system with precedence chain (GAP-02)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AtlasFlowConfig:
    """Merged configuration from precedence chain: env → user → project → defaults."""

    project_root: Path = Path.cwd()

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

    # Git
    worktree_base: str = ""
    isolate_mutating_tasks: bool = True
    worktree_strategy: str = "per-task"

    # Runners
    command_code_timeout_seconds: int = 600
    command_code_max_turns: int = 50

    # MCP
    mcp_enabled: bool = False
    mcp_servers: list[str] = field(default_factory=list)

    # Logging
    log_level: str = "INFO"
    redact_secrets: bool = True

    # Retention
    artifact_retention_days: int = 30
    transcript_retention_days: int = 90

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
                if isinstance(pp, dict):
                    merged["autonomy_mode"] = pp.get("current", merged.get("autonomy_mode"))

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

        # fallbacks.yaml → retry config
        fallback_path = config_dir / "fallbacks.yaml"
        if fallback_path.is_file():
            data = yaml.safe_load(fallback_path.read_text())
            if isinstance(data, dict):
                quality = data.get("quality", {})
                if isinstance(quality, dict):
                    merged["max_retries_per_task"] = quality.get(
                        "max_cross_model_attempts", merged["max_retries_per_task"]
                    )

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
        }
        for env_var, (attr, converter) in env_map.items():
            value = os.environ.get(env_var)
            if value is not None:
                setattr(self, attr, converter(value))
