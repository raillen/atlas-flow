"""Durable storage for discussions and their Decision Ledger (P02).

A discussion is where decisions are made before there is a Goal to hang them
on. Chat context gets compacted and processes restart, so an accepted decision
that lives only in a message list is a decision the project will forget. The
ledger is written down as it happens.
"""

from __future__ import annotations

import json

from atlas_flow.discuss.models import (
    Completeness,
    DecisionCandidate,
    DecisionState,
    DiscussionSession,
    Message,
    ProjectDraft,
)
from atlas_flow.execution.persistence import Persistence

DISCUSS_SCHEMA = """
CREATE TABLE IF NOT EXISTS discussions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discussion_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    content TEXT NOT NULL,
    turn_type TEXT NOT NULL DEFAULT 'message',
    FOREIGN KEY (session_id) REFERENCES discussions(id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    statement TEXT NOT NULL,
    rationale TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    affected_domains TEXT NOT NULL DEFAULT '[]',
    source_message_ids TEXT NOT NULL DEFAULT '[]',
    canonical_targets TEXT NOT NULL DEFAULT '[]',
    supersedes TEXT,
    requires_adr INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES discussions(id)
);

CREATE TABLE IF NOT EXISTS project_drafts (
    session_id TEXT PRIMARY KEY,
    product TEXT NOT NULL,
    architecture TEXT NOT NULL,
    ux TEXT NOT NULL,
    data TEXT NOT NULL,
    security TEXT NOT NULL,
    quality TEXT NOT NULL,
    operations TEXT NOT NULL,
    ai_orchestration TEXT NOT NULL,
    roadmap TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON discussion_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_decisions_session ON decisions(session_id);
"""

DRAFT_DOMAINS = (
    "product", "architecture", "ux", "data", "security",
    "quality", "operations", "ai_orchestration", "roadmap",
)


class DiscussionStore:
    """Reads and writes discussions against the operational database."""

    def __init__(self, persistence: Persistence) -> None:
        self.db = persistence

    async def initialize(self) -> None:
        await self.db.run_script(DISCUSS_SCHEMA)

    async def save_session(self, session: DiscussionSession) -> None:
        """Write the whole session: header, messages, decisions and draft."""
        await self.db.execute(
            """INSERT OR REPLACE INTO discussions (id, project_id, title, started_at)
               VALUES (?, ?, ?, ?)""",
            (session.id, session.project_id, session.title, session.started_at),
        )
        for message in session.messages:
            await self.save_message(session.id, message)
        for decision in session.decisions:
            await self.save_decision(session.id, decision)
        await self.save_draft(session.id, session.draft)

    async def save_message(self, session_id: str, message: Message) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO discussion_messages
                   (id, session_id, timestamp, content, turn_type)
               VALUES (?, ?, ?, ?, ?)""",
            (message.id, session_id, message.timestamp, message.content,
             message.turn_type),
        )

    async def save_decision(self, session_id: str, decision: DecisionCandidate) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO decisions
                   (id, session_id, title, statement, rationale, status, timestamp,
                    affected_domains, source_message_ids, canonical_targets,
                    supersedes, requires_adr)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                decision.id, session_id, decision.title, decision.statement,
                decision.rationale, str(decision.status), decision.timestamp,
                json.dumps(decision.affected_domains),
                json.dumps(decision.source_message_ids),
                json.dumps(decision.canonical_targets),
                decision.supersedes, int(decision.requires_adr),
            ),
        )

    async def save_draft(self, session_id: str, draft: ProjectDraft) -> None:
        await self.db.execute(
            f"""INSERT OR REPLACE INTO project_drafts
                    (session_id, {', '.join(DRAFT_DOMAINS)})
                VALUES ({', '.join('?' * (len(DRAFT_DOMAINS) + 1))})""",
            (session_id, *(str(getattr(draft, name)) for name in DRAFT_DOMAINS)),
        )

    async def load_session(self, session_id: str) -> DiscussionSession | None:
        headers = await self.db.query(
            "SELECT * FROM discussions WHERE id = ?", (session_id,)
        )
        if not headers:
            return None
        header = headers[0]

        return DiscussionSession(
            id=header["id"],
            project_id=header["project_id"],
            title=header["title"],
            started_at=header["started_at"],
            messages=await self._load_messages(session_id),
            decisions=await self._load_decisions(session_id),
            draft=await self._load_draft(session_id),
        )

    async def list_sessions(self, project_id: str | None = None) -> list[str]:
        if project_id is None:
            rows = await self.db.query(
                "SELECT id FROM discussions ORDER BY started_at DESC"
            )
        else:
            rows = await self.db.query(
                "SELECT id FROM discussions WHERE project_id = ? ORDER BY started_at DESC",
                (project_id,),
            )
        return [row["id"] for row in rows]

    async def accepted_decisions(self, session_id: str) -> list[DecisionCandidate]:
        return [
            decision
            for decision in await self._load_decisions(session_id)
            if decision.status == DecisionState.ACCEPTED
        ]

    async def _load_messages(self, session_id: str) -> list[Message]:
        rows = await self.db.query(
            "SELECT * FROM discussion_messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        return [
            Message(
                id=row["id"],
                timestamp=row["timestamp"],
                content=row["content"],
                turn_type=row["turn_type"],
            )
            for row in rows
        ]

    async def _load_decisions(self, session_id: str) -> list[DecisionCandidate]:
        rows = await self.db.query(
            "SELECT * FROM decisions WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        return [
            DecisionCandidate(
                id=row["id"],
                title=row["title"],
                statement=row["statement"],
                rationale=row["rationale"],
                status=DecisionState(row["status"]),
                timestamp=row["timestamp"],
                affected_domains=json.loads(row["affected_domains"]),
                source_message_ids=json.loads(row["source_message_ids"]),
                canonical_targets=json.loads(row["canonical_targets"]),
                supersedes=row["supersedes"],
                requires_adr=bool(row["requires_adr"]),
            )
            for row in rows
        ]

    async def _load_draft(self, session_id: str) -> ProjectDraft:
        rows = await self.db.query(
            "SELECT * FROM project_drafts WHERE session_id = ?", (session_id,)
        )
        if not rows:
            return ProjectDraft(session_id=session_id)
        row = rows[0]
        return ProjectDraft(
            session_id=session_id,
            **{name: Completeness(row[name]) for name in DRAFT_DOMAINS},
        )
