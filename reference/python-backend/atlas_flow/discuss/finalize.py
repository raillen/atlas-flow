"""Finalization pipeline: from discussion to Project Atlas artifacts (P02)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from atlas_flow.discuss.models import (
    Completeness,
    DecisionCandidate,
    DiscussionSession,
    ProjectDraft,
)

ADR_DIRECTORY = "docs/07-decisions"
DECISION_LOG = "docs/01-architecture/DECISION_LEDGER.md"


class ReadinessReport:
    """Gap analysis produced during finalization."""

    def __init__(self, session: DiscussionSession) -> None:
        self.session_id = session.id
        self.gaps = session.draft.gap_report()
        self.ready = session.draft.is_complete()
        self.message_count = len(session.messages)
        self.accepted_decisions = len(
            [d for d in session.decisions if d.status.value == "ACCEPTED"]
        )
        self.total_decisions = len(session.decisions)

    def summary(self) -> str:
        if self.ready:
            return (
                f"Ready: {self.accepted_decisions}/{self.total_decisions}"
                " decisions accepted, all domains sufficient."
            )
        domains = ", ".join(self.gaps)
        return f"Not ready: domains [{domains}] are insufficient ({len(self.gaps)} gaps)."

    def requires_resolution(self) -> list[str]:
        """Return list of domains that need user input before finalization."""
        return list(self.gaps)


@dataclass
class FinalizationResult:
    """Which files finalization created or updated, and where."""

    written: list[Path] = field(default_factory=list)
    adr_count: int = 0

    @property
    def paths(self) -> list[str]:
        return [str(path) for path in self.written]


class FinalizationPipeline:
    """Structured finalization, never a single 'summarize chat' call."""

    @staticmethod
    def analyze(session: DiscussionSession) -> ReadinessReport:
        return ReadinessReport(session)

    @staticmethod
    def validate_draft(draft: ProjectDraft) -> list[str]:
        issues: list[str] = []
        if draft.product == Completeness.UNKNOWN:
            issues.append("Product domain has no input")
        if draft.architecture == Completeness.UNKNOWN:
            issues.append("Architecture domain has no input")
        return issues

    @staticmethod
    def generate_artifacts(session: DiscussionSession) -> dict[str, str]:
        """Render accepted decisions as Project Atlas artifacts, in memory."""
        if not session.draft.is_complete():
            remaining = ", ".join(session.draft.gap_report())
            raise RuntimeError(f"Cannot finalize: domains incomplete: {remaining}")

        artifacts: dict[str, str] = {}
        accepted = [d for d in session.decisions if d.status.value == "ACCEPTED"]

        for index, decision in enumerate(accepted, start=1):
            if not decision.requires_adr:
                continue
            slug = _slug(decision.title)
            artifacts[f"{ADR_DIRECTORY}/ADR-{index:03d}-{slug}.md"] = _render_adr(
                index, decision, session
            )

        artifacts[DECISION_LEDGER_PATH] = _render_ledger(accepted, session)
        return artifacts

    @staticmethod
    def write_artifacts(
        session: DiscussionSession, root: Path, overwrite: bool = False
    ) -> FinalizationResult:
        """Write the artifacts into the project.

        Canonical documentation lives in Git, so finalization has to produce
        files someone can review and commit — a dictionary that never reaches
        disk is a decision the project never actually recorded. Existing files
        are left alone unless overwriting is requested, so re-finalizing cannot
        quietly destroy hand-edited documentation.
        """
        artifacts = FinalizationPipeline.generate_artifacts(session)
        result = FinalizationResult()

        for relative, content in artifacts.items():
            target = root / relative
            if target.exists() and not overwrite:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            result.written.append(target)
            if relative.startswith(ADR_DIRECTORY):
                result.adr_count += 1

        return result


DECISION_LEDGER_PATH = DECISION_LOG


def _slug(title: str) -> str:
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in title)
    return "-".join(cleaned.split()).upper()[:48] or "DECISION"


def _render_adr(index: int, decision: DecisionCandidate, session: DiscussionSession) -> str:
    domains = ", ".join(decision.affected_domains) or "unscoped"
    sources = ", ".join(decision.source_message_ids) or "not linked"
    return f"""# ADR-{index:03d}: {decision.title}

**Status:** Accepted
**Date:** {decision.timestamp[:10]}
**Source:** discussion `{session.id}`

## Decision

{decision.statement}

## Rationale

{decision.rationale}

## Affected domains

{domains}

## Provenance

Derived from discussion messages: {sources}
"""


def _render_ledger(decisions: list[DecisionCandidate], session: DiscussionSession) -> str:
    lines = [
        "# Decision Ledger",
        "",
        f"Generated from discussion `{session.id}` on "
        f"{datetime.now(UTC).date().isoformat()}.",
        "",
        "| Decision | Statement | Domains | ADR |",
        "| --- | --- | --- | --- |",
    ]
    for decision in decisions:
        lines.append(
            f"| {decision.title} | {decision.statement} | "
            f"{', '.join(decision.affected_domains) or '—'} | "
            f"{'yes' if decision.requires_adr else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)
