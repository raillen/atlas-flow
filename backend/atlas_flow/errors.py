"""Structured error framework with retryability and recovery suggestions (GAP-01)."""

from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    CONFIG = "CONFIG"
    PROJECT_ATLAS = "PROJECT_ATLAS"
    GIT = "GIT"
    RUNNER = "RUNNER"
    PROVIDER = "PROVIDER"
    PROTOCOL = "PROTOCOL"
    POLICY = "POLICY"
    VERIFICATION = "VERIFICATION"
    BUDGET = "BUDGET"
    PERSISTENCE = "PERSISTENCE"
    INTERNAL = "INTERNAL"


class Retryability(StrEnum):
    TRANSIENT = "transient"
    FIXABLE = "fixable"
    PERMANENT = "permanent"


SUGGESTED_RECOVERY: dict[ErrorCategory, str] = {
    ErrorCategory.CONFIG: "Check configuration file at .ai/orchestration/ or project overrides.",
    ErrorCategory.PROJECT_ATLAS: "Validate PROJECT_MANIFEST.yaml and .ai/goals/ structure.",
    ErrorCategory.GIT: "Verify repository state, resolve conflicts, retry the operation.",
    ErrorCategory.RUNNER: "Runner unavailable — check runner process/connection and retry.",
    ErrorCategory.PROVIDER: (
        "Model provider error — check credentials, rate limits, or fallback to next model."
    ),
    ErrorCategory.PROTOCOL: "Protocol error — verify ACP/AG-UI/MCP compatibility and retry.",
    ErrorCategory.POLICY: "Policy violation — operation blocked. No automatic retry.",
    ErrorCategory.VERIFICATION: "Gate verification failed — check evidence and repair.",
    ErrorCategory.BUDGET: "Budget exhausted — increase limits or review usage.",
    ErrorCategory.PERSISTENCE: "Database error — check SQLite file integrity and disk space.",
    ErrorCategory.INTERNAL: "Unexpected internal error — report with trace for investigation.",
}


class AtlasFlowError(Exception):
    """Base structured error for Atlas Flow."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        code: str = "E0000",
        retryability: Retryability = Retryability.PERMANENT,
        detail: str = "",
        goal_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        self.category = category
        self.code = code
        self.retryability = retryability
        self.detail = detail
        self.goal_id = goal_id
        self.run_id = run_id
        self.task_id = task_id
        super().__init__(message)

    def can_retry(self) -> bool:
        return self.retryability in (Retryability.TRANSIENT, Retryability.FIXABLE)

    def suggested_recovery(self) -> str:
        base = SUGGESTED_RECOVERY.get(self.category, "No recovery suggestion available.")
        parts = [base]
        if self.goal_id:
            parts.append(f"Goal: {self.goal_id}")
        if self.run_id:
            parts.append(f"Run: {self.run_id}")
        if self.task_id:
            parts.append(f"Task: {self.task_id}")
        if self.detail:
            parts.append(f"Detail: {self.detail}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "code": self.code,
            "message": super().__str__(),
            "retryability": self.retryability,
            "suggested_recovery": self.suggested_recovery(),
            "goal_id": self.goal_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
        }


def config_error(msg: str, code: str = "E0001", **ctx: str | None) -> AtlasFlowError:
    return AtlasFlowError(msg, ErrorCategory.CONFIG, code, Retryability.FIXABLE, **ctx)  # type: ignore[arg-type]


def runner_error(msg: str, code: str = "E0100", **ctx: str | None) -> AtlasFlowError:
    return AtlasFlowError(msg, ErrorCategory.RUNNER, code, Retryability.TRANSIENT, **ctx)  # type: ignore[arg-type]


def provider_error(msg: str, code: str = "E0200", **ctx: str | None) -> AtlasFlowError:
    return AtlasFlowError(msg, ErrorCategory.PROVIDER, code, Retryability.TRANSIENT, **ctx)  # type: ignore[arg-type]


def policy_error(msg: str, code: str = "E0300", **ctx: str | None) -> AtlasFlowError:
    return AtlasFlowError(msg, ErrorCategory.POLICY, code, Retryability.PERMANENT, **ctx)  # type: ignore[arg-type]


def verification_error(msg: str, code: str = "E0400", **ctx: str | None) -> AtlasFlowError:
    return AtlasFlowError(msg, ErrorCategory.VERIFICATION, code, Retryability.FIXABLE, **ctx)  # type: ignore[arg-type]


def persistence_error(msg: str, code: str = "E0500", **ctx: str | None) -> AtlasFlowError:
    return AtlasFlowError(msg, ErrorCategory.PERSISTENCE, code, Retryability.FIXABLE, **ctx)  # type: ignore[arg-type]


def internal_error(msg: str, code: str = "E9999", **ctx: str | None) -> AtlasFlowError:
    return AtlasFlowError(msg, ErrorCategory.INTERNAL, code, Retryability.PERMANENT, **ctx)  # type: ignore[arg-type]
