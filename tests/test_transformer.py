"""Tests for the Markdown transformer."""

from cc_trace.parser import ContentBlock, Message, Session
from cc_trace.transformer import _abstract_code_blocks, transform_session


def test_abstract_code_blocks_python():
    text = "Here is code:\n```python\ndef foo():\n    return 42\n```\nDone."
    result = _abstract_code_blocks(text)
    assert "[Code Block: python, 2 lines]" in result
    assert "def foo" not in result


def test_abstract_code_blocks_no_lang():
    text = "```\nline1\nline2\nline3\n```"
    result = _abstract_code_blocks(text)
    assert "[Code Block: text, 3 lines]" in result


def test_abstract_code_blocks_no_blocks():
    text = "Just some normal text."
    result = _abstract_code_blocks(text)
    assert result == text


def test_frontmatter_basic():
    session = Session(
        session_id="abc12345-dead-beef",
        project="myapp",
        model="claude-opus-4-5-20251101",
        started_at="2026-02-02T10:00:00Z",
        total_input_tokens=1000,
        total_output_tokens=500,
        related_files=["/src/main.py"],
    )
    md = transform_session(session)
    assert "---" in md
    assert "created: 2026-02-02T10:00:00Z" in md
    assert "tokens: 1500" in md
    assert "model: claude-opus-4-5-20251101" in md
    assert "project: myapp" in md
    assert "- /src/main.py" in md
    assert "# Session: myapp (2026-02-02)" in md


def test_thinking_callout():
    session = Session(
        session_id="s1",
        project="test",
        model="m",
        started_at="2026-01-01T00:00:00Z",
        messages=[
            Message(
                role="assistant",
                content_blocks=[
                    ContentBlock(type="thinking", text="Deep thoughts\nLine two"),
                ],
            ),
        ],
    )
    md = transform_session(session)
    assert "> [!thinking]- Thinking" in md
    assert "> Deep thoughts" in md
    assert "> Line two" in md


def test_tool_use_rendering():
    session = Session(
        session_id="s1",
        project="test",
        model="m",
        started_at="2026-01-01T00:00:00Z",
        messages=[
            Message(
                role="assistant",
                content_blocks=[
                    ContentBlock(
                        type="tool_use",
                        tool_name="Read",
                        tool_input={"file_path": "/src/app.py"},
                    ),
                    ContentBlock(
                        type="tool_use",
                        tool_name="Bash",
                        tool_input={"command": "ls -la", "description": "List files"},
                    ),
                ],
            ),
        ],
    )
    md = transform_session(session)
    assert "> 🔧 Used **Read**: `/src/app.py`" in md
    assert "> 🔧 Used **Bash**: List files" in md


def test_user_message_rendering():
    session = Session(
        session_id="s1",
        project="test",
        model="m",
        started_at="2026-01-01T00:00:00Z",
        messages=[
            Message(
                role="user",
                content_blocks=[
                    ContentBlock(type="text", text="Please help me"),
                ],
            ),
        ],
    )
    md = transform_session(session)
    assert "## 🧑 User" in md
    assert "Please help me" in md


def test_related_files_in_frontmatter():
    session = Session(
        session_id="s1",
        project="test",
        model="m",
        started_at="2026-01-01T00:00:00Z",
        related_files=["/a.py", "/b.py"],
    )
    md = transform_session(session)
    assert "related_files:" in md
    assert "  - /a.py" in md
    assert "  - /b.py" in md


def test_no_related_files_omits_key():
    session = Session(
        session_id="s1",
        project="test",
        model="m",
        started_at="2026-01-01T00:00:00Z",
        related_files=[],
    )
    md = transform_session(session)
    assert "related_files:" not in md
