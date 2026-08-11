"""Which MCP servers an agent is allowed to see, and why (P04).

MCP connects agents to external tools and data. That makes the registry a
security boundary rather than a convenience: an agent can only reach a server
this module hands it, so every rule here is a rule about what an agent can
touch.

Four rules, from `docs/01-architecture/MCP_INTEGRATION.md`:

- **Explicit servers.** Nothing is discovered or inferred; a server is
  forwarded only because a file declares it.
- **Per-role allowlists.** A server may name the roles it serves. A role not on
  the list never sees it.
- **Secrets outside the repository.** Environment values are references to
  environment variables, never literals. A declaration carrying a literal value
  is refused, not sanitized — a secret committed to Git is already leaked.
- **Read-only for planning roles.** Roles that plan rather than build get only
  the servers marked read-only.

A server that breaks a rule is skipped with a recorded reason rather than
silently dropped: an agent working without a tool it expected should be able to
find out why.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from atlas_flow.config import AtlasFlowConfig

CONFIG_FILE = "mcp-servers.yaml"

# Roles that reason about work rather than perform it. They get read-only
# servers by default, so a planning pass cannot mutate anything through a tool.
PLANNING_ROLES = frozenset({"goal-planner", "chief-architect", "repo-explorer"})


class McpConfigError(Exception):
    """Raised when the MCP configuration file cannot be understood."""


@dataclass(frozen=True)
class McpServer:
    """One declared server, with its environment already resolved."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    read_only: bool = False
    roles: list[str] = field(default_factory=list)

    def serves(self, role: str) -> bool:
        """An empty role list means the server serves every role."""
        return not self.roles or role in self.roles

    def to_acp(self) -> dict[str, Any]:
        """The shape ACP expects in `session/new`."""
        return {
            "name": self.name,
            "command": self.command,
            "args": list(self.args),
            "env": [
                {"name": key, "value": value} for key, value in sorted(self.env.items())
            ],
        }


@dataclass
class McpRegistry:
    """The servers available to forward, and what was left out."""

    servers: list[McpServer] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    @classmethod
    def load(cls, config: AtlasFlowConfig) -> McpRegistry:
        """Read `.ai/orchestration/mcp-servers.yaml` for a project."""
        path = config.project_root / ".ai" / "orchestration" / CONFIG_FILE
        return cls.from_file(
            path,
            enabled=config.mcp_enabled,
            allowlist=list(config.mcp_servers),
        )

    @classmethod
    def from_file(
        cls,
        path: Path,
        enabled: bool = True,
        allowlist: list[str] | None = None,
    ) -> McpRegistry:
        if not enabled:
            return cls(enabled=False)
        if not path.is_file():
            return cls()

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise McpConfigError(f"{path} must contain a mapping")
        if raw.get("enabled") is False:
            return cls(enabled=False)

        declared = raw.get("servers") or []
        if not isinstance(declared, list):
            raise McpConfigError(f"{path}: 'servers' must be a list")

        registry = cls()
        wanted = set(allowlist or [])
        for entry in declared:
            if not isinstance(entry, dict):
                raise McpConfigError(f"{path}: each server must be a mapping")
            name = str(entry.get("name", "")).strip()
            if not name:
                raise McpConfigError(f"{path}: a server is missing its name")
            if wanted and name not in wanted:
                registry.skipped[name] = "not in the configured server allowlist"
                continue

            command = str(entry.get("command", "")).strip()
            if not command:
                registry.skipped[name] = "no command declared"
                continue

            try:
                resolved = _resolve_env(entry.get("env") or [])
            except _EnvProblem as problem:
                registry.skipped[name] = str(problem)
                continue

            registry.servers.append(
                McpServer(
                    name=name,
                    command=command,
                    args=[str(arg) for arg in entry.get("args") or []],
                    env=resolved,
                    read_only=bool(entry.get("read_only", False)),
                    roles=[str(role) for role in entry.get("roles") or []],
                )
            )
        return registry

    def for_role(self, role: str) -> list[McpServer]:
        """The servers a role may reach, in declaration order."""
        allowed = [server for server in self.servers if server.serves(role)]
        if role in PLANNING_ROLES:
            return [server for server in allowed if server.read_only]
        return allowed

    def acp_servers(self, role: str) -> list[dict[str, Any]]:
        return [server.to_acp() for server in self.for_role(role)]

    def explain(self, role: str) -> str:
        """One line describing what this role got, for logs and evidence."""
        if not self.enabled:
            return "MCP forwarding is disabled"
        granted = [server.name for server in self.for_role(role)]
        parts = [f"forwarded: {', '.join(granted) if granted else 'none'}"]
        if self.skipped:
            parts.append(
                "skipped: "
                + ", ".join(f"{name} ({why})" for name, why in sorted(self.skipped.items()))
            )
        return "; ".join(parts)


class _EnvProblem(Exception):
    pass


def _resolve_env(declared: object) -> dict[str, str]:
    """Turn `[{name, from_env}]` into concrete values.

    A literal `value` is refused rather than accepted: the only way to keep a
    secret out of Git is to never allow it in, and quietly reading one would
    make the rule advisory.
    """
    if not isinstance(declared, list):
        raise _EnvProblem("'env' must be a list of {name, from_env} entries")

    resolved: dict[str, str] = {}
    for entry in declared:
        if not isinstance(entry, dict):
            raise _EnvProblem("'env' must be a list of {name, from_env} entries")
        name = str(entry.get("name", "")).strip()
        if not name:
            raise _EnvProblem("an env entry is missing its name")
        if "value" in entry:
            raise _EnvProblem(
                f"env '{name}' declares a literal value; use from_env so the "
                "secret stays out of the repository"
            )
        source = str(entry.get("from_env", "")).strip()
        if not source:
            raise _EnvProblem(f"env '{name}' declares no from_env source")
        value = os.environ.get(source)
        if value is None:
            raise _EnvProblem(f"environment variable {source} is not set")
        resolved[name] = value
    return resolved
