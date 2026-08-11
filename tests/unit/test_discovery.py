"""P08 runtime model discovery: what the live registry says, and what happens
when it says nothing at all."""

import sys

import pytest

from atlas_flow.routing import discovery
from atlas_flow.routing.discovery import (
    DiscoveryResult,
    ModelRegistry,
    discover_models,
    parse_model_list,
)
from atlas_flow.routing.router import ModelRouter


@pytest.fixture(autouse=True)
def clean_cache() -> object:
    """The registry cache is process-wide; no test may inherit another's."""
    ModelRegistry.reset_cache()
    yield
    ModelRegistry.reset_cache()


def _fake_command(script: str) -> tuple[str, ...]:
    """A stand-in for `cmd --list-models` that behaves however a test needs."""
    return (sys.executable, "-c", script)


class TestParsing:
    def test_identifiers_survive_bullets_and_annotations(self) -> None:
        output = """
        Available models:
          * deepseek/deepseek-v4-pro (default)
          - xiaomi/mimo-v2.5-pro
          • gpt-5.6-luna  [efficient]
        """
        assert parse_model_list(output) == [
            "deepseek/deepseek-v4-pro",
            "xiaomi/mimo-v2.5-pro",
            "gpt-5.6-luna",
        ]

    def test_headings_and_prose_are_not_mistaken_for_models(self) -> None:
        output = "Providers:\nconfigured\n\nnone available\n"
        assert parse_model_list(output) == []

    def test_duplicates_are_reported_once(self) -> None:
        output = "gpt-5.6-luna\ngpt-5.6-luna\n"
        assert parse_model_list(output) == ["gpt-5.6-luna"]


@pytest.mark.asyncio
class TestProbe:
    async def test_a_reachable_registry_reports_its_models(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            discovery, "DISCOVERY_COMMAND",
            _fake_command("print('deepseek/deepseek-v4-pro')\nprint('gpt-5.6-luna')"),
        )

        result = await discover_models(timeout=10)

        assert result.reachable is True
        assert result.degraded is False
        assert result.state == "reachable"
        assert result.available == ["deepseek/deepseek-v4-pro", "gpt-5.6-luna"]
        assert result.probed_at

    async def test_a_missing_harness_degrades_rather_than_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            discovery, "DISCOVERY_COMMAND", ("atlas-flow-no-such-binary",)
        )

        result = await discover_models(timeout=10)

        assert result.degraded is True
        assert result.state == "degraded"
        assert "not on PATH" in result.reason
        assert result.available == []

    async def test_a_failing_harness_reports_its_own_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            discovery, "DISCOVERY_COMMAND",
            _fake_command(
                "import sys; print('no credentials', file=sys.stderr); sys.exit(2)"
            ),
        )

        result = await discover_models(timeout=10)

        assert result.degraded is True
        assert "no credentials" in result.reason

    async def test_a_hanging_harness_is_killed_and_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            discovery, "DISCOVERY_COMMAND", _fake_command("import time; time.sleep(30)")
        )

        result = await discover_models(timeout=0.2)

        assert result.degraded is True
        assert "timed out" in result.reason


@pytest.mark.asyncio
class TestRegistry:
    async def test_before_the_probe_answers_routing_is_pending_not_degraded(self) -> None:
        registry = ModelRegistry(ModelRouter())

        assert registry.probed is False
        assert registry.current.state == "pending"
        # Pending must not be reported as a failure: nothing has failed yet.
        assert registry.current.degraded is False

    async def test_a_successful_probe_narrows_the_router_to_live_models(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            discovery, "DISCOVERY_COMMAND", _fake_command("print('gpt-5.6-luna')")
        )
        router = ModelRouter()
        registry = ModelRegistry(router)

        # On the policy roster alone, a tester routes to the efficient model
        # and a reviewer to a primary one.
        assert router.route("reviewer").selected is not None

        await registry.refresh(timeout=10)

        # Only the efficient model answered. A role that prefers it still
        # routes; a role whose preference list holds only primaries does not —
        # the router does not silently route outside the role's policy.
        tester = router.route("tester").selected
        assert tester is not None and tester.key == "gpt-5.6-luna"
        assert router.route("reviewer").selected is None

    async def test_a_degraded_probe_leaves_the_policy_roster_in_place(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            discovery, "DISCOVERY_COMMAND", ("atlas-flow-no-such-binary",)
        )
        router = ModelRouter()
        registry = ModelRegistry(router)

        result = await registry.refresh(timeout=10)

        assert result.degraded is True
        selected = router.route("core-implementer").selected
        assert selected is not None and selected.key == "mimo-v2.5-pro"

    async def test_the_probe_is_shared_across_registries_in_one_process(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = 0
        real_discover = discovery.discover_models

        async def counting(timeout: float = 15.0) -> DiscoveryResult:
            nonlocal calls
            calls += 1
            return await real_discover(timeout=timeout)

        monkeypatch.setattr(
            discovery, "DISCOVERY_COMMAND", _fake_command("print('gpt-5.6-luna')")
        )
        monkeypatch.setattr(discovery, "discover_models", counting)

        first = ModelRegistry(ModelRouter())
        probe = first.start_background_probe()
        assert probe is not None
        await probe

        second = ModelRegistry(ModelRouter())
        assert second.probed is True
        assert second.start_background_probe() is None
        assert calls == 1

    async def test_a_seeded_result_suppresses_the_subprocess_entirely(self) -> None:
        ModelRegistry.seed(
            DiscoveryResult(available=["gpt-5.6-luna"], reachable=True, reason="seeded")
        )
        router = ModelRouter()
        registry = ModelRegistry(router)

        assert registry.probed is True
        assert registry.start_background_probe() is None
        selected = router.route("tester").selected
        assert selected is not None and selected.key == "gpt-5.6-luna"
