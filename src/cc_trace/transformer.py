"""Transform a parsed Session into Obsidian Markdown."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .parser import ContentBlock, Message, Session

# Regex to match fenced code blocks: ```lang\n...\n```
_CODE_BLOCK_RE = re.compile(
    r"```(\w*)\n(.*?)```",
    re.DOTALL,
)


def _abstract_code_blocks(text: str) -> str:
    """Replace fenced code blocks with a summary placeholder."""

    def _replace(m: re.Match) -> str:
        lang = m.group(1) or "text"
        body = m.group(2)
        line_count = body.count("\n")
        if body and not body.endswith("\n"):
            line_count += 1
        return f"[Code Block: {lang}, {line_count} lines]"

    return _CODE_BLOCK_RE.sub(_replace, text)


def _render_tool_use(block: ContentBlock) -> str:
    """Render a tool_use block as a one-line summary."""
    name = block.tool_name
    inp = block.tool_input

    detail = ""
    if name in ("Read", "Edit", "Write"):
        detail = f"`{inp.get('file_path', '?')}`"
    elif name == "Bash":
        desc = inp.get("description", "")
        cmd = inp.get("command", "")
        detail = desc if desc else (cmd[:60] + "..." if len(cmd) > 60 else cmd)
    elif name in ("Glob", "Grep"):
        pattern = inp.get("pattern", "")
        detail = f"`{pattern}`"
    elif name == "Task":
        detail = inp.get("description", "")
    elif name == "WebSearch":
        detail = inp.get("query", "")
    elif name == "WebFetch":
        detail = inp.get("url", "")
    else:
        # Generic: show first key's value
        for v in inp.values():
            detail = str(v)[:60]
            break

    return f"> 🔧 Used **{name}**: {detail}"


def _render_message(msg: Message) -> list[str]:
    """Render a single message into markdown lines."""
    lines: list[str] = []

    if msg.role == "user":
        lines.append("## 🧑 User")
        lines.append("")
        for block in msg.content_blocks:
            if block.type == "text" and block.text.strip():
                lines.append(_abstract_code_blocks(block.text.strip()))
                lines.append("")
        return lines

    # assistant
    lines.append("## 🤖 Assistant")
    lines.append("")

    for block in msg.content_blocks:
        if block.type == "thinking":
            text = block.text.strip()
            if not text:
                continue
            lines.append("> [!thinking]- Thinking")
            for tl in text.splitlines():
                lines.append(f"> {tl}")
            lines.append("")

        elif block.type == "text":
            text = block.text.strip()
            if not text:
                continue
            lines.append(_abstract_code_blocks(text))
            lines.append("")

        elif block.type == "tool_use":
            lines.append(_render_tool_use(block))
            lines.append("")

    return lines


def _format_timestamp(ts: str) -> str:
    """Normalize a timestamp string to ISO 8601."""
    if not ts:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Try parsing ISO format
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, AttributeError):
        return ts


def transform_session(session: Session) -> str:
    """Transform a Session into an Obsidian Markdown string."""
    created = _format_timestamp(session.started_at)
    total_tokens = session.total_input_tokens + session.total_output_tokens

    # Frontmatter
    lines = [
        "---",
        f"created: {created}",
        "tags:",
        "  - log/claude",
        "  - type/thought_trace",
        "status: auto_generated",
        f"tokens: {total_tokens}",
        f"model: {session.model}",
        f"project: {session.project}",
    ]

    if session.related_files:
        lines.append("related_files:")
        for fp in session.related_files:
            lines.append(f"  - {fp}")

    lines.append("---")
    lines.append("")

    # Title
    date_str = created[:10] if len(created) >= 10 else "unknown"
    lines.append(f"# Session: {session.project} ({date_str})")
    lines.append("")

    # Messages
    for msg in session.messages:
        lines.extend(_render_message(msg))

    return "\n".join(lines)
