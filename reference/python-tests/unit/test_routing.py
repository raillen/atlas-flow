"""P08 Model router tests."""

from atlas_flow.routing.router import ModelRouter


class TestModelRouter:
    def test_route_architect_to_deepseek(self) -> None:
        router = ModelRouter()
        decision = router.route("chief-architect")
        assert decision.selected is not None
        assert decision.selected.key == "deepseek-v4-pro"

    def test_route_falls_back_to_second_preference(self) -> None:
        router = ModelRouter(available_models=["mimo-v2.5-pro"])
        router.probe_available(["mimo-v2.5-pro"])
        decision = router.route("chief-architect")
        assert decision.selected is not None
        assert decision.selected.key == "mimo-v2.5-pro"
        assert decision.fallback_attempts == 1

    def test_luna_not_reachable_without_probe(self) -> None:
        router = ModelRouter(available_models=["deepseek-v4-pro", "mimo-v2.5-pro"])
        router.probe_available(["deepseek-v4-pro", "mimo-v2.5-pro"])
        decision = router.route("tester")
        assert decision.selected is not None
        assert decision.selected.key == "mimo-v2.5-pro"
        assert decision.fallback_attempts == 1

    def test_luna_reachable_when_probed(self) -> None:
        router = ModelRouter(available_models=["gpt-5.6-luna"])
        router.probe_available(["gpt-5.6-luna"])
        decision = router.route("tester")
        assert decision.selected is not None
        assert decision.selected.key == "gpt-5.6-luna"

    def test_cross_provider_reviewer(self) -> None:
        router = ModelRouter(available_models=["deepseek-v4-pro", "mimo-v2.5-pro"])
        router.probe_available(["deepseek-v4-pro", "mimo-v2.5-pro"])
        reviewer = router.select_high_risk_reviewer("deepseek")
        assert reviewer is not None
        assert reviewer.provider != "deepseek"

    def test_why_explanation(self) -> None:
        router = ModelRouter()
        decision = router.route("core-implementer")
        explanation = router.why_this_model(decision)
        assert "core-implementer" in explanation
        assert "mimo" in explanation.lower()

    def test_scorecard_updates(self) -> None:
        router = ModelRouter()
        router.scorecard.observe("deepseek-v4-pro", success=True)
        router.scorecard.observe("deepseek-v4-pro", success=False)
        assert router.scorecard.success_rate("deepseek-v4-pro") == 0.5
        assert router.scorecard.total_uses("deepseek-v4-pro") == 2
