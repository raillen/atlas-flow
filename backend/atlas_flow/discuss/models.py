"""Discuss and Decision Ledger domain models (P02)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DecisionState(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class Completeness(StrEnum):
    UNKNOWN = "unknown"
    PARTIAL = "partial"
    SUFFICIENT = "sufficient"
    LOCKED = "locked"


class ReferenceKind(StrEnum):
    FILE = "file"
    IMAGE = "image"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class MessageReference(BaseModel):
    """A project-local file reference attached to a discussion message."""

    path: str
    kind: ReferenceKind = ReferenceKind.FILE
    label: str = ""
    mime_type: str | None = None


class Message(BaseModel):
    id: str = Field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:12]}")
    timestamp: str = Field(default_factory=_now_iso)
    content: str
    turn_type: str = "message"
    references: list[MessageReference] = Field(default_factory=list)


class DecisionCandidate(BaseModel):
    id: str = Field(default_factory=lambda: f"dec-{uuid.uuid4().hex[:12]}")
    title: str
    statement: str
    rationale: str
    status: DecisionState = DecisionState.PROPOSED
    source_message_ids: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=_now_iso)
    affected_domains: list[str] = Field(default_factory=list)
    supersedes: str | None = None
    requires_adr: bool = False
    canonical_targets: list[str] = Field(default_factory=list)


class ProjectDraft(BaseModel):
    session_id: str = Field(default_factory=lambda: f"draft-{uuid.uuid4().hex[:8]}")
    product: Completeness = Completeness.UNKNOWN
    architecture: Completeness = Completeness.UNKNOWN
    ux: Completeness = Completeness.UNKNOWN
    data: Completeness = Completeness.UNKNOWN
    security: Completeness = Completeness.UNKNOWN
    quality: Completeness = Completeness.UNKNOWN
    operations: Completeness = Completeness.UNKNOWN
    ai_orchestration: Completeness = Completeness.UNKNOWN
    roadmap: Completeness = Completeness.UNKNOWN

    def is_complete(self) -> bool:
        return all(
            getattr(self, field) == Completeness.SUFFICIENT
            for field in type(self).model_fields
            if field != "session_id"
        )

    def gap_report(self) -> dict[str, Completeness]:
        return {
            field: getattr(self, field)
            for field in type(self).model_fields
            if field != "session_id"
            and getattr(self, field) != Completeness.SUFFICIENT
        }


class DiscussionSession(BaseModel):
    id: str = Field(default_factory=lambda: f"session-{uuid.uuid4().hex[:8]}")
    project_id: str
    title: str = ""
    messages: list[Message] = Field(default_factory=list)
    decisions: list[DecisionCandidate] = Field(default_factory=list)
    draft: ProjectDraft = Field(default_factory=ProjectDraft)
    started_at: str = Field(default_factory=_now_iso)
