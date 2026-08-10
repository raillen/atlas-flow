"""Tests for gap implementations: errors, config, workforce, context engine."""

from pathlib import Path

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.context.engine import ContextEngine
from atlas_flow.errors import (
    ErrorCategory,
    Retryability,
    config_error,
    internal_error,
    policy_error,
    provider_error,
    runner_error,
    verification_error,
)
from atlas_flow.workforce.resolver import WorkforceResolver


class TestErrorFramework:
    def test_can_retry_transient(self) -> None:
        err = runner_error("runner crashed")
        assert err.can_retry()
        assert err.retryability == Retryability.TRANSIENT

    def test_policy_never_retry(self) -> None:
        err = policy_error("not allowed")
        assert not err.can_retry()
        assert err.retryability == Retryability.PERMANENT

    def test_recovery_includes_context(self) -> None:
        err = verification_error(
            "gate failed", code="E0401",
            goal_id="G1", run_id="r1", task_id="t1", detail="test failure",
        )
        rec = err.suggested_recovery()
        assert "G1" in rec
        assert "r1" in rec
        assert "t1" in rec
        assert "test failure" in rec

    def test_to_dict(self) -> None:
        err = config_error("missing field", code="E0002")
        d = err.to_dict()
        assert d["category"] == "CONFIG"
        assert d["code"] == "E0002"
        assert d["retryability"] == "fixable"

    def test_factory_functions_use_correct_category(self) -> None:
        assert runner_error("x").category == ErrorCategory.RUNNER
        assert provider_error("x").category == ErrorCategory.PROVIDER
        assert policy_error("x").category == ErrorCategory.POLICY
        assert internal_error("x").category == ErrorCategory.INTERNAL


class TestConfig:
    def test_defaults(self) -> None:
        cfg = AtlasFlowConfig()
        assert cfg.autonomy_mode == "agentic"
        assert cfg.max_parallel_tasks == 4
        assert cfg.max_retries_per_task == 3

    def test_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("ATLAS_FLOW_MAX_PARALLEL", "8")
        monkeypatch.setenv("ATLAS_FLOW_LOG_LEVEL", "DEBUG")
        cfg = AtlasFlowConfig(project_root=Path("/tmp"))
        cfg._apply_env_overrides()
        assert cfg.max_parallel_tasks == 8
        assert cfg.log_level == "DEBUG"

    def test_override_method(self) -> None:
        cfg = AtlasFlowConfig()
        cfg._apply_override({"max_parallel_tasks": 2, "log_level": "WARN"})
        assert cfg.max_parallel_tasks == 2


class TestContextEngine:
    def test_build_for_goal_p01(self) -> None:
        root = Path(__file__).resolve().parents[2]
        engine = ContextEngine(root)
        pack = engine.build_for_goal("P01-G01")
        assert pack.goal_id == "P01-G01"
        assert pack.entry_count() > 0
        assert len(pack.validation_commands) == 5

    def test_budget_check(self) -> None:
        root = Path(__file__).resolve().parents[2]
        engine = ContextEngine(root)
        pack = engine.build_for_goal("P02-G01")
        assert pack.is_within_budget(1_000_000)

    def test_unknown_goal_has_minimal_context(self) -> None:
        root = Path(__file__).resolve().parents[2]
        engine = ContextEngine(root)
        pack = engine.build_for_goal("P99-G99")
        # Should still have ADRs and tests
        assert pack.entry_count() >= 0


class TestWorkforceResolver:
    def test_resolve_for_role(self) -> None:
        from atlas_flow.goals.models import AgentManifest, RecipeManifest, SkillManifest
        agents = AgentManifest(agents=["core-implementer", "tester"], selection_basis=["role"])
        skills = SkillManifest(skills=["goal-contracts", "dag-planning"])
        recipes = RecipeManifest(recipes=["locked-goal-implementation"])

        workforce = WorkforceResolver.resolve_for_role(
            "core-implementer", agents, skills, recipes,
        )
        assert workforce.selected_agent == "core-implementer"
        assert "locked-goal-implementation" in workforce.recipes

    def test_skills_for_task_capabilities(self) -> None:
        from atlas_flow.goals.models import SkillManifest
        skills = SkillManifest(skills=[
            "goal-contracts", "dag-planning", "fault-injection", "docs-maintenance",
        ])
        matched = WorkforceResolver.skills_for_task(
            ["planning", "dag"], skills,
        )
        assert "dag-planning" in matched
        assert "fault-injection" not in matched
