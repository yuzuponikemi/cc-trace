"""Tests for the JSONL parser."""

import json
import tempfile
from pathlib import Path

from cc_trace.parser import parse_session


def _write_jsonl(lines: list[dict], parent_name: str = "proj-myapp") -> Path:
    """Write JSONL lines to a temp file with proper directory structure."""
    tmp = Path(tempfile.mkdtemp()) / parent_name
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / "abc12345-0000-0000-0000-000000000000.jsonl"
    with open(path, "w") as f:
        for record in lines:
            f.write(json.dumps(record) + "\n")
    return path


def test_parse_empty_file():
    path = _write_jsonl([])
    session = parse_session(path)
    assert session.messages == []
    assert session.project == "myapp"


def test_parse_user_message():
    records = [
        {
            "type": "user",
            "userType": "external",
            "sessionId": "sess-001",
            "timestamp": "2026-02-02T10:00:00Z",
            "message": {"role": "user", "content": "Hello, world!"},
        },
    ]
    path = _write_jsonl(records)
    session = parse_session(path)
    assert len(session.messages) == 1
    assert session.messages[0].role == "user"
    assert session.messages[0].content_blocks[0].text == "Hello, world!"
    assert session.session_id == "sess-001"
    assert session.started_at == "2026-02-02T10:00:00Z"


def test_skip_internal_user():
    records = [
        {
            "type": "user",
            "userType": "internal",
            "sessionId": "sess-001",
            "message": {"role": "user", "content": "tool result"},
        },
    ]
    path = _write_jsonl(records)
    session = parse_session(path)
    assert session.messages == []


def test_parse_assistant_thinking_and_text():
    records = [
        {
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-5-20251101",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "content": [
                    {"type": "thinking", "thinking": "Let me think..."},
                ],
            },
        },
        {
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-5-20251101",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "content": [
                    {"type": "text", "text": "Here is my answer."},
                ],
            },
        },
    ]
    path = _write_jsonl(records)
    session = parse_session(path)
    # Both assistant lines should be merged into one message
    assert len(session.messages) == 1
    assert session.messages[0].role == "assistant"
    blocks = session.messages[0].content_blocks
    assert len(blocks) == 2
    assert blocks[0].type == "thinking"
    assert blocks[0].text == "Let me think..."
    assert blocks[1].type == "text"
    assert blocks[1].text == "Here is my answer."
    assert session.model == "claude-opus-4-5-20251101"
    assert session.total_input_tokens == 200
    assert session.total_output_tokens == 100


def test_parse_tool_use_collects_files():
    records = [
        {
            "type": "assistant",
            "message": {
                "model": "test-model",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/src/main.py"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/src/utils.py"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "ls"},
                    },
                ],
            },
        },
    ]
    path = _write_jsonl(records)
    session = parse_session(path)
    assert "/src/main.py" in session.related_files
    assert "/src/utils.py" in session.related_files
    # Bash should not be in related_files
    assert len(session.related_files) == 2


def test_skip_progress_records():
    records = [
        {"type": "progress", "data": "something"},
        {"type": "file-history-snapshot", "snapshot": {}},
    ]
    path = _write_jsonl(records)
    session = parse_session(path)
    assert session.messages == []


def test_user_then_assistant_creates_two_messages():
    records = [
        {
            "type": "user",
            "userType": "external",
            "sessionId": "s1",
            "timestamp": "2026-01-01T00:00:00Z",
            "message": {"role": "user", "content": "Question?"},
        },
        {
            "type": "assistant",
            "message": {
                "model": "m",
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "content": [{"type": "text", "text": "Answer."}],
            },
        },
    ]
    path = _write_jsonl(records)
    session = parse_session(path)
    assert len(session.messages) == 2
    assert session.messages[0].role == "user"
    assert session.messages[1].role == "assistant"
