"""Model router — role-based routing, fallbacks, scorecards (P08)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Priority(StrEnum):
    PRIMARY = "primary"
    EFFICIENT = "efficient-third"


class Availability(StrEnum):
    EXPECTED = "expected"
    PROBE_REQUIRED = "probe-required"


@dataclass
class ModelEntry:
    key: str
    provider: str
    command_code_id: str
    priority: Priority
    availability: Availability


@dataclass
class RouteDecision:
    role: str
    selected: ModelEntry | None = None
    reason: str = ""
    fallback_attempts: int = 0
    candidates: list[ModelEntry] = field(default_factory=list)


class ModelScorecard:
    """Tracks usage observations per model for adaptive scoring (post-MVP)."""

    def __init__(self) -> None:
        self._scores: dict[str, dict[str, float]] = {}

    def observe(
        self, model_key: str, success: bool, latency_ms: float = 0
    ) -> None:
        entry = self._scores.setdefault(model_key, {"uses": 0, "successes": 0, "failures": 0})
        entry["uses"] += 1
        if success:
            entry["successes"] += 1
        else:
            entry["failures"] += 1

    def success_rate(self, model_key: str) -> float:
        entry = self._scores.get(model_key)
        if not entry or entry["uses"] == 0:
            return 0.0
        return entry["successes"] / entry["uses"]

    def total_uses(self, model_key: str) -> int:
        return int(self._scores.get(model_key, {}).get("uses", 0))


class ModelRouter:
    """Deterministic policy-based routing for v0.1."""

    ROSTER: list[ModelEntry] = [
        ModelEntry(
            key="deepseek-v4-pro",
            provider="deepseek",
            command_code_id="deepseek/deepseek-v4-pro",
            priority=Priority.PRIMARY,
            availability=Availability.EXPECTED,
        ),
        ModelEntry(
            key="mimo-v2.5-pro",
            provider="xiaomi",
            command_code_id="xiaomi/mimo-v2.5-pro",
            priority=Priority.PRIMARY,
            availability=Availability.EXPECTED,
        ),
        ModelEntry(
            key="gpt-5.6-luna",
            provider="openai",
            command_code_id="gpt-5.6-luna",
            priority=Priority.EFFICIENT,
            availability=Availability.PROBE_REQUIRED,
        ),
    ]

    ROLE_DEFAULTS: dict[str, list[str]] = {
        "chief-architect": ["deepseek-v4-pro", "mimo-v2.5-pro"],
        "goal-planner": ["deepseek-v4-pro", "mimo-v2.5-pro"],
        "core-implementer": ["mimo-v2.5-pro", "deepseek-v4-pro"],
        "ui-engineer": ["mimo-v2.5-pro", "deepseek-v4-pro"],
        "tester": ["gpt-5.6-luna", "mimo-v2.5-pro"],
        "repo-explorer": ["gpt-5.6-luna", "mimo-v2.5-pro"],
        "reviewer": ["deepseek-v4-pro"],
    }

    def __init__(self, available_models: list[str] | None = None) -> None:
        self._available = set(available_models or [])
        self.scorecard = ModelScorecard()
        self._model_by_key: dict[str, ModelEntry] = {
            m.key: m for m in self.ROSTER
        }

    def probe_available(self, available_ids: list[str]) -> None:
        self._available = set(available_ids)

    def is_reachable(self, entry: ModelEntry) -> bool:
        if not self._available:
            return entry.availability == Availability.EXPECTED
        return any(
            entry.command_code_id in a or entry.key.lower() in a.lower()
            for a in self._available
        )

    def route(self, role: str, task_risk: str = "medium") -> RouteDecision:
        preferred_order = self.ROLE_DEFAULTS.get(
            role,
            ["deepseek-v4-pro", "mimo-v2.5-pro", "gpt-5.6-luna"],
        )

        candidates = [
            self._model_by_key[key]
            for key in preferred_order
            if key in self._model_by_key
        ]

        decision = RouteDecision(role=role, candidates=candidates)

        for idx, candidate in enumerate(candidates):
            if self.is_reachable(candidate):
                decision.selected = candidate
                decision.reason = (
                    f"Selected {candidate.key} ({candidate.provider}) for role"
                    f" '{role}' — index {idx} in preference order"
                )
                decision.fallback_attempts = idx
                return decision

        decision.reason = f"No reachable model for role '{role}'"
        return decision

    def select_high_risk_reviewer(
        self, implementer_provider: str
    ) -> ModelEntry | None:
        cross_providers = [
            r for r in self.ROSTER
            if r.provider != implementer_provider and self.is_reachable(r)
        ]
        if cross_providers:
            primary_cross = [
                r for r in cross_providers
                if r.priority == Priority.PRIMARY
            ]
            return (primary_cross or cross_providers)[0]
        return None

    def why_this_model(self, decision: RouteDecision) -> str:
        if decision.selected is None:
            return f"No model available for role '{decision.role}'"
        return (
            f"Role '{decision.role}' routed to {decision.selected.key}"
            f" ({decision.selected.provider}) — {decision.reason}"
        )
