"""P02 Decision Ledger and finalization tests."""

from pathlib import Path

import pytest

from atlas_flow.discuss.finalize import FinalizationPipeline
from atlas_flow.discuss.ledger import DecisionLedger
from atlas_flow.discuss.models import (
    Completeness,
    DecisionCandidate,
    DecisionState,
    DiscussionSession,
    Message,
)


@pytest.fixture
def session() -> DiscussionSession:
    s = DiscussionSession(project_id="atlas-flow")
    s.messages.append(Message(content="We need a Python backend", turn_type="message"))
    s.messages.append(Message(content="Use FastAPI", turn_type="decision_candidate"))
    return s


@pytest.fixture
def candidate() -> DecisionCandidate:
    return DecisionCandidate(
        title="Use Python/FastAPI backend",
        statement="Backend orchestration uses Python 3.12+ with FastAPI.",
        rationale="Reuse Project Atlas Python ecosystem.",
        affected_domains=["architecture"],
        requires_adr=True,
    )


class TestDecisionLedger:
    def test_propose_accept(self, session: DiscussionSession, candidate: DecisionCandidate) -> None:
        DecisionLedger.propose(session, candidate)
        assert session.decisions[0].status == DecisionState.PROPOSED

        DecisionLedger.accept(session, candidate.id)
        assert session.decisions[0].status == DecisionState.ACCEPTED

    def test_reject(self, session: DiscussionSession, candidate: DecisionCandidate) -> None:
        DecisionLedger.propose(session, candidate)
        DecisionLedger.reject(session, candidate.id)
        assert session.decisions[0].status == DecisionState.REJECTED

    def test_supersede(self, session: DiscussionSession, candidate: DecisionCandidate) -> None:
        DecisionLedger.propose(session, candidate)
        DecisionLedger.accept(session, candidate.id)

        new_candidate = DecisionCandidate(
            title="Use FastAPI + Litestar",
            statement="Use FastAPI with Litestar for hot reload.",
            rationale="Better DX.",
            affected_domains=["architecture"],
        )
        DecisionLedger.supersede(session, candidate.id, new_candidate)
        assert session.decisions[0].status == DecisionState.SUPERSEDED
        assert session.decisions[1].status == DecisionState.PROPOSED
        assert session.decisions[1].supersedes == candidate.id

    def test_cannot_accept_rejected(
        self, session: DiscussionSession, candidate: DecisionCandidate
    ) -> None:
        DecisionLedger.propose(session, candidate)
        DecisionLedger.reject(session, candidate.id)
        with pytest.raises(ValueError, match="Cannot accept"):
            DecisionLedger.accept(session, candidate.id)

    def test_no_decision_lost_when_accepted(
        self, session: DiscussionSession, candidate: DecisionCandidate
    ) -> None:
        DecisionLedger.propose(session, candidate)
        DecisionLedger.accept(session, candidate.id)
        accepted = DecisionLedger.accepted(session)
        assert len(accepted) == 1
        assert accepted[0].id == candidate.id
        # Accepted count remains 1 even when other decisions are rejected
        c2 = DecisionCandidate(title="T2", statement="s", rationale="r", affected_domains=["ux"])
        DecisionLedger.propose(session, c2)
        DecisionLedger.reject(session, c2.id)
        assert len(DecisionLedger.accepted(session)) == 1


class TestProjectDraft:
    def test_unknown_by_default(self) -> None:
        from atlas_flow.discuss.models import ProjectDraft
        draft = ProjectDraft()
        assert draft.product == Completeness.UNKNOWN
        assert not draft.is_complete()

    def test_complete_when_all_sufficient(self) -> None:
        from atlas_flow.discuss.models import ProjectDraft
        draft = ProjectDraft(
            product=Completeness.SUFFICIENT,
            architecture=Completeness.SUFFICIENT,
            ux=Completeness.SUFFICIENT,
            data=Completeness.SUFFICIENT,
            security=Completeness.SUFFICIENT,
            quality=Completeness.SUFFICIENT,
            operations=Completeness.SUFFICIENT,
            ai_orchestration=Completeness.SUFFICIENT,
            roadmap=Completeness.SUFFICIENT,
        )
        assert draft.is_complete()
        assert draft.gap_report() == {}


class TestFinalization:
    def test_analyze_reports_gaps(self, session: DiscussionSession) -> None:
        report = FinalizationPipeline.analyze(session)
        assert not report.ready
        assert "product" in report.gaps

    def test_validate_draft_issues(self) -> None:
        from atlas_flow.discuss.models import ProjectDraft
        draft = ProjectDraft()
        issues = FinalizationPipeline.validate_draft(draft)
        assert len(issues) >= 2
        assert any("Product" in i for i in issues)
        assert any("Architecture" in i for i in issues)

    def test_generate_artifacts_on_complete_draft(self) -> None:
        s = DiscussionSession(project_id="atlas-flow")
        s.draft = type(s.draft)(
            product=Completeness.SUFFICIENT,
            architecture=Completeness.SUFFICIENT,
            ux=Completeness.SUFFICIENT,
            data=Completeness.SUFFICIENT,
            security=Completeness.SUFFICIENT,
            quality=Completeness.SUFFICIENT,
            operations=Completeness.SUFFICIENT,
            ai_orchestration=Completeness.SUFFICIENT,
            roadmap=Completeness.SUFFICIENT,
        )
        d = DecisionCandidate(
            title="Use Python",
            statement="Python backend",
            rationale="Ecosystem",
            affected_domains=["architecture"],
            requires_adr=True,
        )
        DecisionLedger.propose(s, d)
        DecisionLedger.accept(s, d.id)
        artifacts = FinalizationPipeline.generate_artifacts(s)

        # ADRs follow the repository's own naming convention so the generated
        # file sits alongside the hand-written ones.
        assert "docs/07-decisions/ADR-001-USE-PYTHON.md" in artifacts
        assert "docs/01-architecture/DECISION_LEDGER.md" in artifacts

        adr = artifacts["docs/07-decisions/ADR-001-USE-PYTHON.md"]
        assert "# ADR-001: Use Python" in adr
        assert "Python backend" in adr
        assert "Ecosystem" in adr
        assert s.id in adr

    def test_cannot_finalize_incomplete_draft(self, session: DiscussionSession) -> None:
        with pytest.raises(RuntimeError, match="Cannot finalize"):
            FinalizationPipeline.generate_artifacts(session)

    def test_write_artifacts_creates_real_files(self, tmp_path: Path) -> None:
        session = _complete_session()
        result = FinalizationPipeline.write_artifacts(session, tmp_path)

        assert result.adr_count == 1
        adr = tmp_path / "docs/07-decisions/ADR-001-USE-PYTHON.md"
        ledger = tmp_path / "docs/01-architecture/DECISION_LEDGER.md"
        assert adr.is_file()
        assert ledger.is_file()
        assert "Use Python" in ledger.read_text(encoding="utf-8")
        assert set(result.paths) == {str(adr), str(ledger)}

    def test_write_artifacts_does_not_clobber_existing_documentation(
        self, tmp_path: Path
    ) -> None:
        """Re-finalizing must not destroy documentation someone edited."""
        session = _complete_session()
        ledger = tmp_path / "docs/01-architecture/DECISION_LEDGER.md"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("# Hand written\n", encoding="utf-8")

        result = FinalizationPipeline.write_artifacts(session, tmp_path)

        assert ledger.read_text(encoding="utf-8") == "# Hand written\n"
        assert str(ledger) not in result.paths

        overwritten = FinalizationPipeline.write_artifacts(
            session, tmp_path, overwrite=True
        )
        assert str(ledger) in overwritten.paths
        assert "Use Python" in ledger.read_text(encoding="utf-8")

    def test_rejected_decisions_are_not_written(self, tmp_path: Path) -> None:
        session = _complete_session()
        rejected = DecisionCandidate(
            title="Use Perl", statement="no", rationale="no", requires_adr=True
        )
        DecisionLedger.propose(session, rejected)
        DecisionLedger.reject(session, rejected.id)

        FinalizationPipeline.write_artifacts(session, tmp_path)
        written = [p.name for p in (tmp_path / "docs/07-decisions").glob("*.md")]
        assert written == ["ADR-001-USE-PYTHON.md"]


def _complete_session() -> DiscussionSession:
    session = DiscussionSession(project_id="atlas-flow")
    session.draft = type(session.draft)(
        **{
            domain: Completeness.SUFFICIENT
            for domain in (
                "product", "architecture", "ux", "data", "security",
                "quality", "operations", "ai_orchestration", "roadmap",
            )
        }
    )
    decision = DecisionCandidate(
        title="Use Python",
        statement="Python backend",
        rationale="Ecosystem",
        affected_domains=["architecture"],
        requires_adr=True,
    )
    DecisionLedger.propose(session, decision)
    DecisionLedger.accept(session, decision.id)
    return session
