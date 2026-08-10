#!/usr/bin/env python3
"""A minimal ACP agent used to test the client against a real process.

Behaviour is driven by environment variables so one script can stand in for
several kinds of agent:

    ACP_FIXTURE_MODE
        "basic"       answer prompts with text (default)
        "permission"  ask for permission before answering
        "no_session"  advertise no loadSession capability and refuse resume
        "error"       reply to session/prompt with a JSON-RPC error
        "noisy"       print a non-JSON line before answering
        "old"         claim a protocol version this client cannot speak
"""

import json
import os
import sys

MODE = os.environ.get("ACP_FIXTURE_MODE", "basic")


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def reply(request_id: int, result: dict) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "result": result})


def fail(request_id: int, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def notify(method: str, params: dict) -> None:
    send({"jsonrpc": "2.0", "method": method, "params": params})


def read() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {}


def handle_initialize(request_id: int) -> None:
    if MODE == "old":
        reply(request_id, {"protocolVersion": 99, "agentCapabilities": {}})
        return
    reply(
        request_id,
        {
            "protocolVersion": 1,
            "agentCapabilities": {
                "loadSession": MODE != "no_session",
                "promptCapabilities": {"image": True, "audio": False},
            },
        },
    )


def request_permission(session_id: str) -> dict:
    """Ask the client for permission and block until it answers."""
    send({
        "jsonrpc": "2.0",
        "id": 9001,
        "method": "session/request_permission",
        "params": {
            "sessionId": session_id,
            "toolCall": {"title": "write_file", "kind": "edit"},
            "options": [
                {"optionId": "yes", "name": "Allow once", "kind": "allow_once"},
                {"optionId": "no", "name": "Reject", "kind": "reject_once"},
            ],
        },
    })

    while True:
        message = read()
        if message is None:
            return {}
        if message.get("id") == 9001:
            return message.get("result") or {}


def handle_prompt(request_id: int, params: dict) -> None:
    session_id = params.get("sessionId", "")

    if MODE == "error":
        fail(request_id, -32000, "agent refused the prompt")
        return

    if MODE == "noisy":
        sys.stdout.write("warning: this line is not JSON\n")
        sys.stdout.flush()

    granted = True
    if MODE == "permission":
        outcome = request_permission(session_id).get("outcome", {})
        granted = outcome.get("outcome") == "selected" and outcome.get("optionId") == "yes"

    text = "work done" if granted else "blocked without permission"
    notify(
        "session/update",
        {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": text},
            },
        },
    )
    reply(request_id, {"stopReason": "end_turn"})


def main() -> None:
    session_counter = 0

    while True:
        message = read()
        if message is None:
            return
        method = message.get("method")
        request_id = message.get("id")

        if method == "initialize" and request_id is not None:
            handle_initialize(request_id)
        elif method == "session/new" and request_id is not None:
            session_counter += 1
            reply(request_id, {"sessionId": f"fixture-session-{session_counter}"})
        elif method == "session/load" and request_id is not None:
            if MODE == "no_session":
                fail(request_id, -32601, "loadSession not supported")
            else:
                reply(request_id, {})
        elif method == "session/prompt" and request_id is not None:
            handle_prompt(request_id, message.get("params") or {})
        elif method == "session/cancel":
            continue
        elif request_id is not None:
            fail(request_id, -32601, f"Method not found: {method}")


if __name__ == "__main__":
    main()
