"""P02: the Decision Ledger survives compaction and restarts."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from atlas_flow.discuss.ledger import DecisionLedger
from atlas_flow.discuss.models import (
    Completeness,
    DecisionCandidate,
    DecisionState,
    DiscussionSession,
    Message,
    MessageReference,
    ReferenceKind,
)
from atlas_flow.discuss.store import DiscussionStore
from atlas_flow.execution.persistence import Persistence


@pytest_asyncio.fixture
async def store(tmp_path: Path) -> AsyncIterator[tuple[DiscussionStore, Path]]:
    db_path = tmp_path / "state.db"
    persistence = Persistence(db_path)
    await persistence.initialize()
    discussion_store = DiscussionStore(persistence)
    await discussion_store.initialize()
    try:
        yield discussion_store, db_path
    finally:
        await persistence.close()


def _session_with_decisions() -> DiscussionSession:
    session = DiscussionSession(project_id="atlas-flow", title="Kickoff")
    session.messages.append(Message(content="We need a Python backend"))
    session.messages[0].references.append(
        MessageReference(path="docs/ATLAS.md", kind=ReferenceKind.FILE)
    )
    session.messages.append(Message(content="Agreed", turn_type="decision_candidate"))

    accepted = DecisionCandidate(
        title="Python backend",
        statement="The orchestration core is written in Python",
        rationale="Reuses Project Atlas tooling",
        affected_domains=["architecture"],
        requires_adr=True,
    )
    rejected = DecisionCandidate(
        title="Mongo", statement="Use MongoDB", rationale="none given"
    )
    DecisionLedger.propose(session, accepted)
    DecisionLedger.propose(session, rejected)
    DecisionLedger.accept(session, accepted.id)
    DecisionLedger.reject(session, rejected.id)

    session.draft.product = Completeness.SUFFICIENT
    session.draft.architecture = Completeness.PARTIAL
    return session


@pytest.mark.asyncio
class TestDiscussionStore:
    async def test_session_round_trips(
        self, store: tuple[DiscussionStore, Path]
    ) -> None:
        discussion_store, _ = store
        session = _session_with_decisions()
        await discussion_store.save_session(session)

        loaded = await discussion_store.load_session(session.id)

        assert loaded is not None
        assert loaded.title == "Kickoff"
        assert [m.content for m in loaded.messages] == [
            m.content for m in session.messages
        ]
        assert loaded.messages[0].references[0].path == "docs/ATLAS.md"
        assert len(loaded.decisions) == 2
        assert loaded.draft.product == Completeness.SUFFICIENT
        assert loaded.draft.architecture == Completeness.PARTIAL

    async def test_decision_details_are_preserved(
        self, store: tuple[DiscussionStore, Path]
    ) -> None:
        discussion_store, _ = store
        session = _session_with_decisions()
        await discussion_store.save_session(session)

        loaded = await discussion_store.load_session(session.id)
        assert loaded is not None
        accepted = next(d for d in loaded.decisions if d.status == DecisionState.ACCEPTED)

        assert accepted.title == "Python backend"
        assert accepted.rationale == "Reuses Project Atlas tooling"
        assert accepted.affected_domains == ["architecture"]
        assert accepted.requires_adr is True

    async def test_accepted_decisions_survive_a_restart(self, tmp_path: Path) -> None:
        """The acceptance criterion: no accepted decision is lost.

        The chat transcript can be compacted away and the process can die; what
        the project agreed to has to still be there afterwards.
        """
        db_path = tmp_path / "state.db"
        session = _session_with_decisions()

        first = Persistence(db_path)
        await first.initialize()
        first_store = DiscussionStore(first)
        await first_store.initialize()
        await first_store.save_session(session)
        await first.close()

        second = Persistence(db_path)
        await second.initialize()
        try:
            second_store = DiscussionStore(second)
            accepted = await second_store.accepted_decisions(session.id)

            assert [d.title for d in accepted] == ["Python backend"]

            # Even with every message dropped, the ledger stands on its own.
            reloaded = await second_store.load_session(session.id)
            assert reloaded is not None
            assert len(reloaded.decisions) == 2
        finally:
            await second.close()

    async def test_superseding_a_decision_is_recorded(
        self, store: tuple[DiscussionStore, Path]
    ) -> None:
        discussion_store, _ = store
        session = _session_with_decisions()
        original = next(d for d in session.decisions if d.status == DecisionState.ACCEPTED)

        replacement = DecisionCandidate(
            title="Rust backend",
            statement="Rewrite the core in Rust",
            rationale="Changed our minds",
            supersedes=original.id,
        )
        DecisionLedger.propose(session, replacement)
        DecisionLedger.accept(session, replacement.id)
        await discussion_store.save_session(session)

        loaded = await discussion_store.load_session(session.id)
        assert loaded is not None
        stored = next(d for d in loaded.decisions if d.title == "Rust backend")
        assert stored.supersedes == original.id

    async def test_unknown_session_is_none(
        self, store: tuple[DiscussionStore, Path]
    ) -> None:
        discussion_store, _ = store
        assert await discussion_store.load_session("session-nope") is None

    async def test_sessions_are_listed_per_project(
        self, store: tuple[DiscussionStore, Path]
    ) -> None:
        discussion_store, _ = store
        mine = DiscussionSession(project_id="atlas-flow")
        theirs = DiscussionSession(project_id="other-project")
        await discussion_store.save_session(mine)
        await discussion_store.save_session(theirs)

        assert await discussion_store.list_sessions("atlas-flow") == [mine.id]
        assert len(await discussion_store.list_sessions()) == 2

    async def test_saving_twice_does_not_duplicate_rows(
        self, store: tuple[DiscussionStore, Path]
    ) -> None:
        discussion_store, _ = store
        session = _session_with_decisions()
        await discussion_store.save_session(session)
        await discussion_store.save_session(session)

        loaded = await discussion_store.load_session(session.id)
        assert loaded is not None
        assert len(loaded.messages) == len(session.messages)
        assert len(loaded.decisions) == len(session.decisions)
