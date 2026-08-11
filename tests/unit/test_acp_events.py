"""P04 event normalization: one closed vocabulary out of many agent dialects."""

from atlas_flow.acp.events import UpdateKind, normalize_update


def tool_call(**overrides: object) -> dict:
    base = {
        "sessionUpdate": "tool_call",
        "toolCallId": "call-1",
        "title": "do the thing",
        "status": "completed",
    }
    base.update(overrides)
    return base


class TestMessages:
    def test_an_agent_message_becomes_a_message_event(self) -> None:
        event = normalize_update(
            {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "working on it"},
            }
        )

        assert event is not None
        assert event.kind == UpdateKind.MESSAGE
        assert event.text == "working on it"
        assert event.event_name == "atlas.agent.message"

    def test_thoughts_are_distinguished_from_messages(self) -> None:
        event = normalize_update(
            {
                "sessionUpdate": "agent_thought_chunk",
                "content": {"type": "text", "text": "maybe try X"},
            }
        )

        assert event is not None and event.kind == UpdateKind.THOUGHT

    def test_an_empty_chunk_publishes_nothing(self) -> None:
        assert normalize_update({"sessionUpdate": "agent_message_chunk"}) is None

    def test_an_unknown_update_is_dropped_rather_than_forwarded_untyped(self) -> None:
        """Forwarding a blob would leak one agent's vocabulary downstream."""
        assert normalize_update({"sessionUpdate": "vendor_specific_thing"}) is None
        assert normalize_update({}) is None


class TestTerminal:
    def test_an_execute_call_becomes_terminal_output(self) -> None:
        event = normalize_update(
            tool_call(
                kind="execute",
                title="pytest -q",
                content=[
                    {"type": "terminal", "content": {"type": "text", "text": "2 passed\n"}}
                ],
            )
        )

        assert event is not None
        assert event.kind == UpdateKind.TERMINAL
        assert event.text == "2 passed\n"
        assert event.tool == "pytest -q"
        assert event.status == "completed"
        assert event.event_name == "atlas.terminal.output"

    def test_terminal_content_is_recognized_without_an_execute_kind(self) -> None:
        """Agents that do not label the call kind still stream terminal blocks."""
        event = normalize_update(
            tool_call(
                content=[
                    {"type": "terminal", "content": {"type": "text", "text": "hello"}}
                ]
            )
        )

        assert event is not None and event.kind == UpdateKind.TERMINAL
        assert event.text == "hello"

    def test_an_execute_call_with_no_output_yet_still_reports_the_command(self) -> None:
        event = normalize_update(tool_call(kind="execute", status="in_progress"))

        assert event is not None
        assert event.kind == UpdateKind.TERMINAL
        assert event.text == ""
        assert event.status == "in_progress"


class TestFiles:
    def test_an_edit_reports_the_paths_it_touched(self) -> None:
        event = normalize_update(
            tool_call(
                kind="edit",
                locations=[{"path": "backend/auth.py"}],
                content=[
                    {"type": "diff", "path": "backend/auth.py", "newText": "x"},
                    {"type": "diff", "path": "backend/session.py", "newText": "y"},
                ],
            )
        )

        assert event is not None
        assert event.kind == UpdateKind.FILE
        assert event.paths == ["backend/auth.py", "backend/session.py"]
        assert event.text == "2 file diff(s)"
        assert event.event_name == "atlas.file.changed"

    def test_a_diff_is_recognized_without_an_edit_kind(self) -> None:
        event = normalize_update(
            tool_call(content=[{"type": "diff", "path": "a.py", "newText": "x"}])
        )

        assert event is not None and event.kind == UpdateKind.FILE
        assert event.paths == ["a.py"]

    def test_a_delete_with_no_diff_is_still_a_file_change(self) -> None:
        event = normalize_update(
            tool_call(kind="delete", locations=[{"path": "old.py"}])
        )

        assert event is not None
        assert event.kind == UpdateKind.FILE
        assert event.paths == ["old.py"]


class TestOther:
    def test_an_unclassified_tool_call_is_still_reported_as_a_tool_call(self) -> None:
        event = normalize_update(tool_call(kind="think"))

        assert event is not None
        assert event.kind == UpdateKind.TOOL
        assert event.tool == "do the thing"

    def test_a_nameless_tool_call_publishes_nothing(self) -> None:
        assert normalize_update(
            {"sessionUpdate": "tool_call", "kind": "think"}
        ) is None

    def test_a_plan_update_is_summarized(self) -> None:
        event = normalize_update(
            {
                "sessionUpdate": "plan",
                "entries": [
                    {"content": "read the code", "status": "completed"},
                    {"content": "write the fix", "status": "pending"},
                ],
            }
        )

        assert event is not None
        assert event.kind == UpdateKind.PLAN
        assert event.text == "read the code; write the fix"

    def test_the_payload_carries_everything_a_client_renders(self) -> None:
        event = normalize_update(
            tool_call(kind="edit", locations=[{"path": "a.py"}])
        )

        assert event is not None
        assert event.payload() == {
            "kind": "file",
            "text": "",
            "paths": ["a.py"],
            "tool": "do the thing",
            "status": "completed",
        }


class TestRedaction:
    def test_a_token_in_agent_output_never_leaves_the_boundary(self) -> None:
        event = normalize_update(
            {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "using ghp_0123456789abcdefghij"},
            }
        )

        assert event is not None
        assert "ghp_0123456789abcdefghij" not in event.text
        assert "REDACTED" in event.text

    def test_terminal_output_is_redacted_too(self) -> None:
        event = normalize_update(
            tool_call(
                kind="execute",
                content=[
                    {
                        "type": "terminal",
                        "content": {"type": "text", "text": "export TOKEN=sk-abcdefghijklmnop"},
                    }
                ],
            )
        )

        assert event is not None
        assert "sk-abcdefghijklmnop" not in event.text
