"""Finalization pipeline: from discussion to Project Atlas artifacts (P02)."""

from atlas_flow.discuss.models import (
    Completeness,
    DiscussionSession,
    ProjectDraft,
)


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
        """Convert accepted decisions and draft into Project Atlas artifact stubs."""
        if not session.draft.is_complete():
            remaining = ", ".join(session.draft.gap_report())
            raise RuntimeError(
                f"Cannot finalize: domains incomplete: {remaining}"
            )

        artifacts: dict[str, str] = {}
        for decision in session.decisions:
            if decision.status.value == "ACCEPTED" and decision.requires_adr:
                artifacts[f"adr-{decision.id}.md"] = (
                    f"# {decision.title}\n\n{decision.statement}\n\n"
                    f"**Rationale:** {decision.rationale}\n"
                    f"**Domains:** {', '.join(decision.affected_domains)}\n"
                )

        return artifacts
