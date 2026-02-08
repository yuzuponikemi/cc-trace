"""Tests for Gemini transformer (HTML to Markdown + document generation)."""

from __future__ import annotations

from cc_trace.gemini.takeout_parser import TakeoutEntry
from cc_trace.gemini.transformer import (
    Conversation,
    html_to_markdown,
    make_output_filename,
    transform_conversation,
)


# --- HTML to Markdown conversion tests ---


def test_html_to_markdown_empty() -> None:
    """Empty input returns empty output."""
    assert html_to_markdown("") == ""


def test_html_to_markdown_paragraph() -> None:
    """Paragraphs are converted correctly."""
    html = "<p>First paragraph.</p><p>Second paragraph.</p>"
    result = html_to_markdown(html)
    assert "First paragraph." in result
    assert "Second paragraph." in result


def test_html_to_markdown_bold_italic() -> None:
    """Bold and italic formatting is converted."""
    html = "<p>This is <strong>bold</strong> and <em>italic</em> text.</p>"
    result = html_to_markdown(html)
    assert "**bold**" in result
    assert "*italic*" in result


def test_html_to_markdown_headings() -> None:
    """Headings are converted to Markdown headings."""
    html = "<h1>Title</h1><h2>Subtitle</h2><h3>Section</h3>"
    result = html_to_markdown(html)
    assert "# Title" in result
    assert "## Subtitle" in result
    assert "### Section" in result


def test_html_to_markdown_unordered_list() -> None:
    """Unordered lists are converted."""
    html = "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"
    result = html_to_markdown(html)
    assert "- Item 1" in result
    assert "- Item 2" in result
    assert "- Item 3" in result


def test_html_to_markdown_ordered_list() -> None:
    """Ordered lists are converted with numbers."""
    html = "<ol><li>First</li><li>Second</li><li>Third</li></ol>"
    result = html_to_markdown(html)
    assert "1. First" in result
    assert "2. Second" in result
    assert "3. Third" in result


def test_html_to_markdown_inline_code() -> None:
    """Inline code is converted with backticks."""
    html = "<p>Use the <code>print()</code> function.</p>"
    result = html_to_markdown(html)
    assert "`print()`" in result


def test_html_to_markdown_code_block() -> None:
    """Code blocks are converted with fenced code blocks."""
    html = "<pre><code>def hello():\n    print('world')</code></pre>"
    result = html_to_markdown(html)
    assert "```" in result
    assert "def hello():" in result


def test_html_to_markdown_link() -> None:
    """Links are converted to Markdown links."""
    html = '<p>Visit <a href="https://example.com">our site</a> for more.</p>'
    result = html_to_markdown(html)
    assert "[our site](https://example.com)" in result


def test_html_to_markdown_table() -> None:
    """Tables are converted to Markdown tables."""
    html = """
    <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>Alpha</td><td>1</td></tr>
        <tr><td>Beta</td><td>2</td></tr>
    </table>
    """
    result = html_to_markdown(html)
    assert "| Name | Value |" in result
    assert "| Alpha | 1 |" in result
    assert "| Beta | 2 |" in result
    # Check separator line exists
    assert "---" in result


def test_html_to_markdown_html_entities() -> None:
    """HTML entities are unescaped."""
    html = "<p>Less than: &lt; Greater than: &gt; Ampersand: &amp;</p>"
    result = html_to_markdown(html)
    assert "Less than: <" in result
    assert "Greater than: >" in result
    assert "Ampersand: &" in result


def test_html_to_markdown_nested_list() -> None:
    """Nested lists are indented correctly."""
    html = """
    <ul>
        <li>Parent 1
            <ul>
                <li>Child 1</li>
                <li>Child 2</li>
            </ul>
        </li>
        <li>Parent 2</li>
    </ul>
    """
    result = html_to_markdown(html)
    assert "- Parent 1" in result
    assert "  - Child 1" in result
    assert "  - Child 2" in result
    assert "- Parent 2" in result


# --- Conversation transformation tests ---


def _make_entry(
    prompt: str,
    response: str = "<p>Response</p>",
    timestamp: str = "2026-01-15T10:00:00.000Z",
    gem_name: str = "",
    attached_files: list[str] | None = None,
) -> TakeoutEntry:
    """Helper to create TakeoutEntry for testing."""
    return TakeoutEntry(
        prompt_text=prompt,
        response_html=response,
        timestamp=timestamp,
        gem_name=gem_name,
        attached_files=attached_files or [],
    )


def test_transform_single_turn() -> None:
    """Single turn conversation is transformed correctly."""
    entry = _make_entry("What is Python?", "<p>Python is a programming language.</p>")
    conversation = Conversation(
        conversation_id="abc12345xyz",
        title="Python question",
        entries=[entry],
    )

    result = transform_conversation(conversation)

    # Check frontmatter
    assert "created: 2026-01-15T10:00:00.000Z" in result
    assert "tags:" in result
    assert "  - log/gemini" in result
    assert "conversation_id: abc12345xyz" in result
    assert "turns: 1" in result

    # Check title
    assert "# Gemini: Python question (2026-01-15)" in result

    # Check content
    assert "## User" in result
    assert "What is Python?" in result
    assert "## Gemini" in result
    assert "Python is a programming language." in result


def test_transform_multiple_turns() -> None:
    """Multiple turn conversation is transformed correctly."""
    entries = [
        _make_entry("First question", "<p>First answer</p>", "2026-01-15T10:00:00.000Z"),
        _make_entry("Second question", "<p>Second answer</p>", "2026-01-15T10:05:00.000Z"),
    ]
    conversation = Conversation(
        conversation_id="multi123",
        title="Multi-turn chat",
        entries=entries,
    )

    result = transform_conversation(conversation)

    assert "turns: 2" in result
    assert "First question" in result
    assert "First answer" in result
    assert "Second question" in result
    assert "Second answer" in result


def test_transform_with_gem() -> None:
    """Gem usage is noted in output."""
    entry = _make_entry("Test prompt", gem_name="MyCustomGem")
    conversation = Conversation(
        conversation_id="gem123",
        title="Gem test",
        entries=[entry],
    )

    result = transform_conversation(conversation)
    assert "> [!note] Used Gem: MyCustomGem" in result


def test_transform_with_attached_files() -> None:
    """Attached files are noted in output."""
    entry = _make_entry("Test prompt", attached_files=["image.png", "doc.pdf"])
    conversation = Conversation(
        conversation_id="files123",
        title="Files test",
        entries=[entry],
    )

    result = transform_conversation(conversation)
    assert "> [!info] Attached files: image.png, doc.pdf" in result


def test_transform_no_response() -> None:
    """Entry without response shows placeholder."""
    entry = _make_entry("Test prompt", response="")
    conversation = Conversation(
        conversation_id="noresponse123",
        title="No response",
        entries=[entry],
    )

    result = transform_conversation(conversation)
    assert "*No response*" in result


# --- Filename generation tests ---


def test_make_output_filename() -> None:
    """Filename is generated correctly."""
    entry = _make_entry("Test", timestamp="2026-01-15T10:00:00.000Z")
    conversation = Conversation(
        conversation_id="abcdefgh12345678",
        title="Test",
        entries=[entry],
    )

    filename = make_output_filename(conversation)
    assert filename == "GEM-2026-01-15-abcdefgh.md"


def test_make_output_filename_short_id() -> None:
    """Short conversation IDs are handled."""
    entry = _make_entry("Test", timestamp="2026-02-20T12:00:00.000Z")
    conversation = Conversation(
        conversation_id="short",
        title="Test",
        entries=[entry],
    )

    filename = make_output_filename(conversation)
    assert filename == "GEM-2026-02-20-short.md"
