"""Budget limits for a run (P08).

What can be enforced depends on what the runner reports. A subprocess harness
does not necessarily hand back token counts, so this ledger enforces two
different kinds of limit and is explicit about which is which:

- **Attempts** are always countable, so the attempt cap always applies. It is
  what actually stops a runaway retry loop.
- **Tokens and cost** are only enforced for the usage a runner reports. A run
  whose runner reports nothing is not silently assumed to be free — the ledger
  reports that its spend is unmeasured, so a caller can refuse to proceed
  rather than trusting a zero it never observed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from atlas_flow.config import AtlasFlowConfig
from atlas_flow.harness.runner import RunnerResult


class BudgetKind(StrEnum):
    ATTEMPTS = "attempts"
    TOKENS = "tokens"
    COST = "cost"


class BudgetExceeded(Exception):
    """Raised when a run has spent what it was allowed to spend."""

    def __init__(self, kind: BudgetKind, spent: float, limit: float) -> None:
        self.kind = kind
        self.spent = spent
        self.limit = limit
        super().__init__(
            f"Budget exceeded: {kind} spent {spent:g} of {limit:g} allowed"
        )


@dataclass
class Usage:
    """Usage a runner reported for one attempt."""

    tokens: int = 0
    cost_usd: float = 0.0
    reported: bool = False

    @staticmethod
    def from_result(result: RunnerResult) -> Usage:
        """Read usage out of a runner's evidence, if it provided any."""
        tokens = _as_int(result.evidence.get("tokens"))
        cost = _as_float(result.evidence.get("cost_usd"))
        return Usage(
            tokens=tokens or 0,
            cost_usd=cost or 0.0,
            reported=tokens is not None or cost is not None,
        )


@dataclass
class BudgetLedger:
    """Tracks one run's spend against its configured limits."""

    max_attempts: int
    max_tokens: int
    max_cost_usd: float

    attempts: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    unmeasured_attempts: int = 0
    exceeded: list[str] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: AtlasFlowConfig, task_count: int) -> BudgetLedger:
        """Derive an attempt cap from the retry policy and the plan size.

        Every task may be tried once and retried up to the configured limit, so
        anything beyond that is a loop rather than a plan.
        """
        per_task = 1 + max(0, config.max_retries_per_task)
        return cls(
            max_attempts=max(1, task_count) * per_task,
            max_tokens=config.max_tokens_per_run,
            max_cost_usd=config.max_cost_per_run_usd,
        )

    @property
    def has_unmeasured_spend(self) -> bool:
        return self.unmeasured_attempts > 0

    def remaining_attempts(self) -> int:
        return max(0, self.max_attempts - self.attempts)

    def check_can_start_attempt(self) -> None:
        """Raise before starting work that the budget cannot pay for."""
        if self.attempts >= self.max_attempts:
            raise BudgetExceeded(BudgetKind.ATTEMPTS, self.attempts, self.max_attempts)
        if self.max_tokens and self.tokens >= self.max_tokens:
            raise BudgetExceeded(BudgetKind.TOKENS, self.tokens, self.max_tokens)
        if self.max_cost_usd and self.cost_usd >= self.max_cost_usd:
            raise BudgetExceeded(BudgetKind.COST, self.cost_usd, self.max_cost_usd)

    def record(self, usage: Usage) -> None:
        self.attempts += 1
        if not usage.reported:
            self.unmeasured_attempts += 1
            return
        self.tokens += usage.tokens
        self.cost_usd += usage.cost_usd

    def would_exceed(self) -> BudgetKind | None:
        """Which limit is already spent, if any."""
        if self.attempts >= self.max_attempts:
            return BudgetKind.ATTEMPTS
        if self.max_tokens and self.tokens >= self.max_tokens:
            return BudgetKind.TOKENS
        if self.max_cost_usd and self.cost_usd >= self.max_cost_usd:
            return BudgetKind.COST
        return None

    def summary(self) -> dict[str, object]:
        return {
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "tokens": self.tokens,
            "max_tokens": self.max_tokens,
            "cost_usd": round(self.cost_usd, 4),
            "max_cost_usd": self.max_cost_usd,
            "unmeasured_attempts": self.unmeasured_attempts,
            "spend_is_measured": not self.has_unmeasured_spend,
        }


def _as_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None
