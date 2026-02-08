"""Transform Gemini conversations to Obsidian Markdown.

Converts HTML responses to Markdown and generates frontmatter.
Uses Python standard library only (html.parser).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cc_trace.gemini.takeout_parser import TakeoutEntry


@dataclass
class Conversation:
    """A Gemini conversation with matched entries."""

    conversation_id: str
    title: str
    entries: list[TakeoutEntry] = field(default_factory=list)

    @property
    def created_at(self) -> str:
        """Return the timestamp of the first entry."""
        if self.entries:
            return self.entries[0].timestamp
        return ""

    @property
    def turn_count(self) -> int:
        """Return the number of turns (prompts) in this conversation."""
        return len(self.entries)


class HTMLToMarkdownConverter(HTMLParser):
    """Convert HTML to Markdown using Python's html.parser."""

    def __init__(self) -> None:
        super().__init__()
        self._output: list[str] = []
        self._list_stack: list[str] = []  # 'ul' or 'ol'
        self._list_counters: list[int] = []
        self._in_code_block = False
        self._code_lang = ""
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._cell_content = ""
        self._in_cell = False
        self._link_href = ""
        self._in_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)

        if tag == "p":
            self._output.append("\n")
        elif tag == "strong" or tag == "b":
            self._output.append("**")
        elif tag == "em" or tag == "i":
            self._output.append("*")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self._output.append("\n" + "#" * level + " ")
        elif tag == "ul":
            self._list_stack.append("ul")
            self._output.append("\n")
        elif tag == "ol":
            self._list_stack.append("ol")
            self._list_counters.append(0)
            self._output.append("\n")
        elif tag == "li":
            indent = "  " * (len(self._list_stack) - 1)
            if self._list_stack and self._list_stack[-1] == "ol":
                self._list_counters[-1] += 1
                self._output.append(f"{indent}{self._list_counters[-1]}. ")
            else:
                self._output.append(f"{indent}- ")
        elif tag == "code":
            # Check if inside a pre block
            if not self._in_code_block:
                self._output.append("`")
        elif tag == "pre":
            self._in_code_block = True
            # Check for language hint in class
            code_class = attrs_dict.get("class", "") or ""
            match = re.search(r"language-(\w+)", code_class)
            self._code_lang = match.group(1) if match else ""
            self._output.append(f"\n```{self._code_lang}\n")
        elif tag == "a":
            self._link_href = attrs_dict.get("href", "") or ""
            self._in_link = True
            self._output.append("[")
        elif tag == "br":
            self._output.append("\n")
        elif tag == "table":
            self._in_table = True
            self._table_rows = []
        elif tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._cell_content = ""
        elif tag == "hr":
            self._output.append("\n---\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self._output.append("\n")
        elif tag == "strong" or tag == "b":
            self._output.append("**")
        elif tag == "em" or tag == "i":
            self._output.append("*")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._output.append("\n")
        elif tag == "ul":
            if self._list_stack:
                self._list_stack.pop()
            self._output.append("\n")
        elif tag == "ol":
            if self._list_stack:
                self._list_stack.pop()
            if self._list_counters:
                self._list_counters.pop()
            self._output.append("\n")
        elif tag == "li":
            self._output.append("\n")
        elif tag == "code":
            if not self._in_code_block:
                self._output.append("`")
        elif tag == "pre":
            self._in_code_block = False
            self._output.append("\n```\n")
        elif tag == "a":
            self._in_link = False
            self._output.append(f"]({self._link_href})")
            self._link_href = ""
        elif tag == "table":
            self._in_table = False
            self._output.append(self._render_table())
        elif tag == "tr":
            self._table_rows.append(self._current_row)
        elif tag in ("td", "th"):
            self._in_cell = False
            self._current_row.append(self._cell_content.strip())

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_content += data
        else:
            self._output.append(data)

    def _render_table(self) -> str:
        """Render collected table rows as Markdown table."""
        if not self._table_rows:
            return ""

        lines = []
        for i, row in enumerate(self._table_rows):
            line = "| " + " | ".join(row) + " |"
            lines.append(line)
            if i == 0:
                # Add separator after header
                sep = "| " + " | ".join("-" * max(3, len(cell)) for cell in row) + " |"
                lines.append(sep)

        return "\n" + "\n".join(lines) + "\n"

    def get_markdown(self) -> str:
        """Return the converted Markdown text."""
        text = "".join(self._output)
        # Clean up excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_markdown(html_content: str) -> str:
    """Convert HTML to Markdown.

    Args:
        html_content: HTML string to convert.

    Returns:
        Markdown formatted string.
    """
    if not html_content:
        return ""

    # Unescape HTML entities first
    html_content = html.unescape(html_content)

    parser = HTMLToMarkdownConverter()
    parser.feed(html_content)
    return parser.get_markdown()


def transform_conversation(conversation: Conversation) -> str:
    """Transform a conversation to Obsidian Markdown.

    Args:
        conversation: Conversation object with matched entries.

    Returns:
        Complete Markdown document string.
    """
    lines: list[str] = []

    # Frontmatter
    lines.append("---")
    lines.append(f"created: {conversation.created_at}")
    lines.append("tags:")
    lines.append("  - log/gemini")
    lines.append("  - type/thought_trace")
    lines.append("status: auto_generated")
    lines.append(f"conversation_id: {conversation.conversation_id}")
    lines.append("source: gemini_takeout")
    lines.append(f"turns: {conversation.turn_count}")
    lines.append("---")
    lines.append("")

    # Title
    date_str = conversation.created_at[:10] if conversation.created_at else "unknown"
    lines.append(f"# Gemini: {conversation.title} ({date_str})")
    lines.append("")

    # Turns
    for entry in conversation.entries:
        # User prompt
        lines.append("## User")
        lines.append(entry.prompt_text)
        lines.append("")

        # Gemini response
        lines.append("## Gemini")
        if entry.response_html:
            md_response = html_to_markdown(entry.response_html)
            lines.append(md_response)
        else:
            lines.append("*No response*")
        lines.append("")

        # Note Gem usage if any
        if entry.gem_name:
            lines.append(f"> [!note] Used Gem: {entry.gem_name}")
            lines.append("")

        # Note attached files if any
        if entry.attached_files:
            files_str = ", ".join(entry.attached_files)
            lines.append(f"> [!info] Attached files: {files_str}")
            lines.append("")

    return "\n".join(lines)


def make_output_filename(conversation: Conversation) -> str:
    """Generate output filename for a conversation.

    Format: GEM-{date}-{conversation_id_first_8}.md

    Args:
        conversation: Conversation object.

    Returns:
        Filename string.
    """
    date_str = conversation.created_at[:10] if conversation.created_at else "unknown"
    short_id = conversation.conversation_id[:8]
    return f"GEM-{date_str}-{short_id}.md"
