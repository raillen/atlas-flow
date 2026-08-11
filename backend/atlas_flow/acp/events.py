"""Normalizing ACP session updates into Atlas Flow events (P04).

An agent narrates its work through `session/update` notifications, and every
agent shapes them slightly differently. This module turns that stream into a
small closed set of records the rest of the runtime can act on, so nothing
downstream has to know the wire vocabulary of a particular agent.

What survives normalization is what an operator needs to answer three
questions: what is the agent saying, what did it run, and what did it change.
An update that answers none of those is dropped rather than forwarded as an
untyped blob.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from atlas_flow.security.guard import SecurityGuard

# Terminal output arrives either as a content block of type "terminal" or, in
# agents that predate that block, as the output of an "execute" tool call.
EXECUTE_KINDS = frozenset({"execute", "terminal", "shell"})
EDIT_KINDS = frozenset({"edit", "write", "create", "delete", "move"})


class UpdateKind(StrEnum):
    MESSAGE = "message"
    THOUGHT = "thought"
    TERMINAL = "terminal"
    FILE = "file"
    TOOL = "tool"
    PLAN = "plan"


# The AG-UI event name each kind is broadcast under.
EVENT_NAMES: dict[UpdateKind, str] = {
    UpdateKind.MESSAGE: "atlas.agent.message",
    UpdateKind.THOUGHT: "atlas.agent.thought",
    UpdateKind.TERMINAL: "atlas.terminal.output",
    UpdateKind.FILE: "atlas.file.changed",
    UpdateKind.TOOL: "atlas.tool.call",
    UpdateKind.PLAN: "atlas.plan.updated",
}


@dataclass
class NormalizedUpdate:
    """One thing the agent said, ran, or changed."""

    kind: UpdateKind
    text: str = ""
    paths: list[str] = field(default_factory=list)
    tool: str = ""
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def event_name(self) -> str:
        return EVENT_NAMES[self.kind]

    def payload(self) -> dict[str, object]:
        return {
            "kind": str(self.kind),
            "text": self.text,
            "paths": list(self.paths),
            "tool": self.tool,
            "status": self.status,
        }


def normalize_update(update: dict[str, Any]) -> NormalizedUpdate | None:
    """Turn one `session/update` payload into a record, or None if it says nothing.

    Text is redacted here, at the boundary where agent output enters the
    runtime. Doing it later would mean choosing which of the several consumers
    to protect; doing it here means none of them ever sees a secret.
    """
    event = _classify(update)
    if event is not None and event.text:
        event.text = SecurityGuard.redact_secrets(event.text)
    return event


def _classify(update: dict[str, Any]) -> NormalizedUpdate | None:
    session_update = str(update.get("sessionUpdate", ""))

    if session_update in ("agent_message_chunk", "user_message_chunk"):
        text = _content_text(update.get("content"))
        return (
            NormalizedUpdate(kind=UpdateKind.MESSAGE, text=text, raw=update)
            if text
            else None
        )

    if session_update == "agent_thought_chunk":
        text = _content_text(update.get("content"))
        return (
            NormalizedUpdate(kind=UpdateKind.THOUGHT, text=text, raw=update)
            if text
            else None
        )

    if session_update == "plan":
        return NormalizedUpdate(
            kind=UpdateKind.PLAN,
            text=_plan_summary(update.get("entries")),
            raw=update,
        )

    if session_update in ("tool_call", "tool_call_update"):
        return _normalize_tool_call(update)

    return None


def _normalize_tool_call(update: dict[str, Any]) -> NormalizedUpdate | None:
    kind = str(update.get("kind", "")).lower()
    title = str(update.get("title", "")) or str(update.get("toolCallId", ""))
    status = str(update.get("status", ""))
    contents = update.get("content")
    blocks = contents if isinstance(contents, list) else []

    terminal_text = "".join(
        _content_text(block.get("content") if isinstance(block, dict) else None)
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "terminal"
    )
    diffs = [block for block in blocks if _is_diff(block)]
    paths = _paths(update, diffs)

    if kind in EXECUTE_KINDS or terminal_text:
        return NormalizedUpdate(
            kind=UpdateKind.TERMINAL,
            text=terminal_text or _content_text(update.get("rawOutput")),
            tool=title,
            status=status,
            raw=update,
        )

    if kind in EDIT_KINDS or diffs:
        return NormalizedUpdate(
            kind=UpdateKind.FILE,
            text=_diff_summary(diffs),
            paths=paths,
            tool=title,
            status=status,
            raw=update,
        )

    if not title:
        return None
    return NormalizedUpdate(
        kind=UpdateKind.TOOL, tool=title, status=status, paths=paths, raw=update
    )


def _is_diff(block: object) -> bool:
    return isinstance(block, dict) and block.get("type") == "diff"


def _paths(update: dict[str, Any], diffs: list[Any]) -> list[str]:
    """Every file the call names, from its locations and its diffs."""
    found: list[str] = []
    locations = update.get("locations")
    if isinstance(locations, list):
        for location in locations:
            if isinstance(location, dict) and location.get("path"):
                found.append(str(location["path"]))
    for diff in diffs:
        if isinstance(diff, dict) and diff.get("path"):
            found.append(str(diff["path"]))
    # Order matters for readability; duplicates do not.
    return list(dict.fromkeys(found))


def _diff_summary(diffs: list[Any]) -> str:
    if not diffs:
        return ""
    return f"{len(diffs)} file diff(s)"


def _plan_summary(entries: object) -> str:
    if not isinstance(entries, list):
        return ""
    return "; ".join(
        str(entry.get("content", ""))
        for entry in entries
        if isinstance(entry, dict) and entry.get("content")
    )


def _content_text(content: object) -> str:
    """Text out of an ACP content block, a list of them, or a bare string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_content_text(item) for item in content)
    if isinstance(content, dict):
        if content.get("type") in (None, "text") and "text" in content:
            return str(content["text"])
        if "output" in content:
            return str(content["output"])
        if "content" in content:
            return _content_text(content["content"])
    return ""
