"""Decision Ledger: accept, reject, supersede decision candidates (P02)."""

from atlas_flow.discuss.models import (
    DecisionCandidate,
    DecisionState,
    DiscussionSession,
)


class DecisionLedger:
    """Manages decision lifecycle within a discussion session."""

    @staticmethod
    def propose(session: DiscussionSession, candidate: DecisionCandidate) -> None:
        existing = {d.id for d in session.decisions}
        if candidate.id in existing:
            raise ValueError(f"Decision {candidate.id} already exists")
        session.decisions.append(candidate)

    @staticmethod
    def accept(session: DiscussionSession, decision_id: str) -> DecisionCandidate:
        decision = DecisionLedger._find(session, decision_id)
        if decision.status != DecisionState.PROPOSED:
            raise ValueError(
                f"Cannot accept decision {decision_id} in state {decision.status}"
            )
        decision.status = DecisionState.ACCEPTED
        return decision

    @staticmethod
    def reject(session: DiscussionSession, decision_id: str) -> DecisionCandidate:
        decision = DecisionLedger._find(session, decision_id)
        if decision.status not in (DecisionState.PROPOSED, DecisionState.ACCEPTED):
            raise ValueError(
                f"Cannot reject decision {decision_id} in state {decision.status}"
            )
        decision.status = DecisionState.REJECTED
        return decision

    @staticmethod
    def supersede(
        session: DiscussionSession, old_id: str, new_candidate: DecisionCandidate
    ) -> DecisionCandidate:
        old = DecisionLedger._find(session, old_id)
        if old.status != DecisionState.ACCEPTED:
            raise ValueError(
                f"Cannot supersede decision {old_id} in state {old.status} — must be ACCEPTED"
            )
        old.status = DecisionState.SUPERSEDED
        new_candidate.supersedes = old_id
        session.decisions.append(new_candidate)
        return new_candidate

    @staticmethod
    def _find(session: DiscussionSession, decision_id: str) -> DecisionCandidate:
        for d in session.decisions:
            if d.id == decision_id:
                return d
        raise KeyError(f"Decision {decision_id} not found in session {session.id}")

    @staticmethod
    def accepted(session: DiscussionSession) -> list[DecisionCandidate]:
        return [d for d in session.decisions if d.status == DecisionState.ACCEPTED]
