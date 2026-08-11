"""P04 MCP registry: an agent reaches only what the registry hands it."""

from pathlib import Path

import pytest

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.mcp.registry import McpConfigError, McpRegistry


def write_config(path: Path, body: str) -> Path:
    target = path / "mcp-servers.yaml"
    target.write_text(body, encoding="utf-8")
    return target


TWO_SERVERS = """
enabled: true
servers:
  - name: docs
    command: mcp-docs
    args: ["--stdio"]
    read_only: true
  - name: deploy
    command: mcp-deploy
    read_only: false
"""


class TestLoading:
    def test_a_missing_file_yields_an_empty_registry(self, tmp_path: Path) -> None:
        registry = McpRegistry.from_file(tmp_path / "absent.yaml")

        assert registry.servers == []
        assert registry.enabled is True

    def test_servers_are_read_in_declaration_order(self, tmp_path: Path) -> None:
        registry = McpRegistry.from_file(write_config(tmp_path, TWO_SERVERS))

        assert [s.name for s in registry.servers] == ["docs", "deploy"]
        assert registry.servers[0].args == ["--stdio"]
        assert registry.servers[0].read_only is True

    def test_disabling_forwarding_hands_out_nothing(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, TWO_SERVERS)

        assert McpRegistry.from_file(path, enabled=False).for_role("tester") == []
        assert McpRegistry.from_file(path).for_role("tester") != []

    def test_an_in_file_disable_also_stops_forwarding(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, "enabled: false\nservers:\n  - name: a\n    command: b\n")

        assert McpRegistry.from_file(path).for_role("tester") == []

    def test_the_config_allowlist_narrows_what_is_forwarded(self, tmp_path: Path) -> None:
        registry = McpRegistry.from_file(
            write_config(tmp_path, TWO_SERVERS), allowlist=["docs"]
        )

        assert [s.name for s in registry.servers] == ["docs"]
        assert "allowlist" in registry.skipped["deploy"]

    def test_a_malformed_file_is_an_error_not_a_silent_empty_registry(
        self, tmp_path: Path
    ) -> None:
        path = write_config(tmp_path, "servers:\n  - just a string\n")

        with pytest.raises(McpConfigError):
            McpRegistry.from_file(path)

    def test_a_server_without_a_command_is_skipped_with_a_reason(
        self, tmp_path: Path
    ) -> None:
        registry = McpRegistry.from_file(
            write_config(tmp_path, "servers:\n  - name: broken\n")
        )

        assert registry.servers == []
        assert registry.skipped["broken"] == "no command declared"


class TestSecrets:
    def test_a_literal_secret_is_refused_rather_than_forwarded(
        self, tmp_path: Path
    ) -> None:
        """Reading it would make "secrets outside the repo" advisory."""
        registry = McpRegistry.from_file(
            write_config(
                tmp_path,
                "servers:\n"
                "  - name: github\n"
                "    command: mcp-github\n"
                "    env:\n"
                "      - name: TOKEN\n"
                "        value: ghp_hardcoded\n",
            )
        )

        assert registry.servers == []
        assert "literal value" in registry.skipped["github"]

    def test_environment_references_are_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ATLAS_TEST_TOKEN", "s3cret")
        registry = McpRegistry.from_file(
            write_config(
                tmp_path,
                "servers:\n"
                "  - name: github\n"
                "    command: mcp-github\n"
                "    env:\n"
                "      - name: TOKEN\n"
                "        from_env: ATLAS_TEST_TOKEN\n",
            )
        )

        assert registry.servers[0].env == {"TOKEN": "s3cret"}
        assert registry.servers[0].to_acp()["env"] == [
            {"name": "TOKEN", "value": "s3cret"}
        ]

    def test_an_unset_variable_skips_the_server_rather_than_forwarding_it_broken(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ATLAS_TEST_ABSENT", raising=False)
        registry = McpRegistry.from_file(
            write_config(
                tmp_path,
                "servers:\n"
                "  - name: github\n"
                "    command: mcp-github\n"
                "    env:\n"
                "      - name: TOKEN\n"
                "        from_env: ATLAS_TEST_ABSENT\n",
            )
        )

        assert registry.servers == []
        assert "ATLAS_TEST_ABSENT is not set" in registry.skipped["github"]


class TestRoleRules:
    def test_a_role_allowlist_hides_the_server_from_everyone_else(
        self, tmp_path: Path
    ) -> None:
        registry = McpRegistry.from_file(
            write_config(
                tmp_path,
                "servers:\n"
                "  - name: deploy\n"
                "    command: mcp-deploy\n"
                "    roles: [core-implementer]\n",
            )
        )

        assert [s.name for s in registry.for_role("core-implementer")] == ["deploy"]
        assert registry.for_role("tester") == []

    def test_planning_roles_only_ever_get_read_only_servers(
        self, tmp_path: Path
    ) -> None:
        registry = McpRegistry.from_file(write_config(tmp_path, TWO_SERVERS))

        assert [s.name for s in registry.for_role("goal-planner")] == ["docs"]
        assert [s.name for s in registry.for_role("chief-architect")] == ["docs"]
        # An implementer builds, so it gets the mutating server too.
        assert [s.name for s in registry.for_role("core-implementer")] == [
            "docs", "deploy",
        ]

    def test_the_explanation_names_what_was_granted_and_what_was_skipped(
        self, tmp_path: Path
    ) -> None:
        registry = McpRegistry.from_file(
            write_config(
                tmp_path,
                TWO_SERVERS + "  - name: broken\n    command: ''\n",
            )
        )

        explanation = registry.explain("goal-planner")
        assert "forwarded: docs" in explanation
        assert "broken (no command declared)" in explanation

    def test_a_disabled_registry_says_so(self, tmp_path: Path) -> None:
        registry = McpRegistry.from_file(
            write_config(tmp_path, TWO_SERVERS), enabled=False
        )

        assert registry.explain("tester") == "MCP forwarding is disabled"


class TestProjectLoading:
    def test_load_reads_the_project_orchestration_directory(
        self, tmp_path: Path
    ) -> None:
        orchestration = tmp_path / ".ai" / "orchestration"
        orchestration.mkdir(parents=True)
        write_config(orchestration, TWO_SERVERS)

        config = AtlasFlowConfig(project_root=tmp_path)
        config.mcp_enabled = True

        registry = McpRegistry.load(config)
        assert [s.name for s in registry.servers] == ["docs", "deploy"]

    def test_forwarding_is_off_unless_the_project_turns_it_on(
        self, tmp_path: Path
    ) -> None:
        """MCP reaches external systems, so it is opt-in."""
        orchestration = tmp_path / ".ai" / "orchestration"
        orchestration.mkdir(parents=True)
        write_config(orchestration, TWO_SERVERS)

        registry = McpRegistry.load(AtlasFlowConfig(project_root=tmp_path))
        assert registry.enabled is False
        assert registry.for_role("core-implementer") == []
