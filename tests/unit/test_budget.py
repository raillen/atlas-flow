"""P08 budget limits: what a run is allowed to spend, and what it can honestly
claim to have measured."""

from pathlib import Path

import pytest

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.execution.budget import (
    BudgetExceeded,
    BudgetKind,
    BudgetLedger,
    Usage,
)
from atlas_flow.harness.runner import RunnerResult


def _result(**evidence: str) -> RunnerResult:
    return RunnerResult(task_id="t1", success=True, evidence=dict(evidence))


class TestUsage:
    def test_reported_tokens_and_cost_are_read_from_evidence(self) -> None:
        usage = Usage.from_result(_result(tokens="1200", cost_usd="0.42"))

        assert usage == Usage(tokens=1200, cost_usd=0.42, reported=True)

    def test_partial_reporting_still_counts_as_reported(self) -> None:
        usage = Usage.from_result(_result(tokens="500"))

        assert usage.reported is True
        assert usage.cost_usd == 0.0

    def test_a_silent_runner_is_not_assumed_to_be_free(self) -> None:
        usage = Usage.from_result(_result(output="done"))

        assert usage.reported is False
        assert (usage.tokens, usage.cost_usd) == (0, 0.0)

    def test_unparseable_numbers_are_treated_as_unreported(self) -> None:
        usage = Usage.from_result(_result(tokens="lots", cost_usd="cheap"))

        assert usage.reported is False


class TestLedgerDerivation:
    def test_the_attempt_cap_follows_the_retry_policy_and_the_plan_size(
        self, tmp_path: Path
    ) -> None:
        config = AtlasFlowConfig(project_root=tmp_path)
        config.max_retries_per_task = 2

        ledger = BudgetLedger.from_config(config, task_count=4)

        # Four tasks, each allowed one try plus two retries.
        assert ledger.max_attempts == 12

    def test_an_empty_plan_still_gets_a_positive_cap(self, tmp_path: Path) -> None:
        config = AtlasFlowConfig(project_root=tmp_path)

        assert BudgetLedger.from_config(config, task_count=0).max_attempts >= 1


class TestEnforcement:
    def test_the_attempt_cap_stops_a_runaway_loop(self) -> None:
        ledger = BudgetLedger(max_attempts=2, max_tokens=0, max_cost_usd=0)

        ledger.check_can_start_attempt()
        ledger.record(Usage(reported=False))
        ledger.check_can_start_attempt()
        ledger.record(Usage(reported=False))

        with pytest.raises(BudgetExceeded) as raised:
            ledger.check_can_start_attempt()
        assert raised.value.kind == BudgetKind.ATTEMPTS
        assert ledger.remaining_attempts() == 0

    def test_reported_tokens_stop_the_run_before_the_attempt_cap_does(self) -> None:
        ledger = BudgetLedger(max_attempts=100, max_tokens=1000, max_cost_usd=0)

        ledger.record(Usage(tokens=1000, reported=True))

        assert ledger.would_exceed() == BudgetKind.TOKENS
        with pytest.raises(BudgetExceeded) as raised:
            ledger.check_can_start_attempt()
        assert raised.value.kind == BudgetKind.TOKENS

    def test_reported_cost_stops_the_run(self) -> None:
        ledger = BudgetLedger(max_attempts=100, max_tokens=0, max_cost_usd=1.0)

        ledger.record(Usage(cost_usd=0.6, reported=True))
        ledger.check_can_start_attempt()
        ledger.record(Usage(cost_usd=0.6, reported=True))

        with pytest.raises(BudgetExceeded) as raised:
            ledger.check_can_start_attempt()
        assert raised.value.kind == BudgetKind.COST

    def test_a_zero_limit_disables_that_dimension(self) -> None:
        """Only the attempt cap is unconditional; 0 means "not configured"."""
        ledger = BudgetLedger(max_attempts=10, max_tokens=0, max_cost_usd=0)

        ledger.record(Usage(tokens=10_000_000, cost_usd=999.0, reported=True))

        assert ledger.would_exceed() is None

    def test_unmeasured_attempts_are_reported_rather_than_counted_as_zero(self) -> None:
        ledger = BudgetLedger(max_attempts=10, max_tokens=1000, max_cost_usd=1.0)

        ledger.record(Usage(tokens=100, reported=True))
        ledger.record(Usage(reported=False))

        summary = ledger.summary()
        assert summary["attempts"] == 2
        assert summary["tokens"] == 100
        assert summary["unmeasured_attempts"] == 1
        # The run cannot claim it stayed under a token budget it never saw.
        assert summary["spend_is_measured"] is False
        assert ledger.has_unmeasured_spend is True
