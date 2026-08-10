"""P02 Decision Ledger and finalization tests."""

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
        assert len(artifacts) >= 1
        assert any(d.id in k for k in artifacts)

    def test_cannot_finalize_incomplete_draft(self, session: DiscussionSession) -> None:
        with pytest.raises(RuntimeError, match="Cannot finalize"):
            FinalizationPipeline.generate_artifacts(session)
