"""Parse Claude Code JSONL session logs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ContentBlock:
    """A single content block within an assistant message."""

    type: str  # "text", "thinking", "tool_use"
    text: str = ""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)


@dataclass
class Message:
    """A parsed message (user or assistant turn)."""

    role: str  # "user" or "assistant"
    content_blocks: list[ContentBlock] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class Session:
    """A fully parsed session."""

    session_id: str = ""
    project: str = ""
    model: str = ""
    started_at: str = ""
    messages: list[Message] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    related_files: list[str] = field(default_factory=list)


def _extract_project_name(path: Path) -> str:
    """Extract a short project name from the JSONL file path.

    Path pattern: ~/.claude/projects/-Users-ikmx-source-personal-PROJECT/SESSION.jsonl
    """
    parent_name = path.parent.name  # e.g. "-Users-ikmx-source-personal-cc-trace"
    parts = parent_name.split("-")
    # Take the last meaningful segment(s)
    # Filter out empty strings and common path segments
    meaningful = [p for p in parts if p and p.lower() not in ("users",)]
    if meaningful:
        return meaningful[-1]
    return parent_name


def _parse_user_content(content: Any) -> list[ContentBlock]:
    """Parse user message content (can be str or list)."""
    if isinstance(content, str):
        return [ContentBlock(type="text", text=content)]
    if isinstance(content, list):
        blocks = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    blocks.append(ContentBlock(type="text", text=item.get("text", "")))
                # Skip tool_result blocks from user messages
        return blocks
    return []


def _parse_assistant_content(content: list[dict]) -> list[ContentBlock]:
    """Parse assistant message content blocks."""
    blocks = []
    if not isinstance(content, list):
        return blocks
    for item in content:
        if not isinstance(item, dict):
            continue
        block_type = item.get("type", "")
        if block_type == "text":
            blocks.append(ContentBlock(type="text", text=item.get("text", "")))
        elif block_type == "thinking":
            blocks.append(ContentBlock(type="thinking", text=item.get("thinking", "")))
        elif block_type == "tool_use":
            blocks.append(ContentBlock(
                type="tool_use",
                tool_name=item.get("name", ""),
                tool_input=item.get("input", {}),
            ))
    return blocks


def parse_session(path: Path) -> Session:
    """Parse a JSONL session file into a Session object.

    Multiple assistant lines for the same turn are merged (streaming chunks).
    """
    session = Session()
    session.project = _extract_project_name(path)
    seen_files: set[str] = set()

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            rec_type = record.get("type")

            if rec_type == "user":
                user_type = record.get("userType", "")
                if user_type != "external":
                    continue

                if not session.session_id:
                    session.session_id = record.get("sessionId", "")
                if not session.started_at:
                    ts = record.get("timestamp")
                    if ts:
                        session.started_at = ts

                content = record.get("message", {}).get("content", "")
                blocks = _parse_user_content(content)
                if blocks:
                    msg = Message(
                        role="user",
                        content_blocks=blocks,
                        timestamp=record.get("timestamp", ""),
                    )
                    session.messages.append(msg)

            elif rec_type == "assistant":
                message_data = record.get("message", {})

                # Extract model info
                model = message_data.get("model", "")
                if model and not session.model:
                    session.model = model

                # Accumulate token usage
                usage = message_data.get("usage", {})
                session.total_input_tokens += usage.get("input_tokens", 0)
                session.total_output_tokens += usage.get("output_tokens", 0)

                # Parse content blocks
                content = message_data.get("content", [])
                blocks = _parse_assistant_content(content)
                if not blocks:
                    continue

                # Collect file paths from tool_use blocks
                for block in blocks:
                    if block.type == "tool_use" and block.tool_name in (
                        "Read", "Edit", "Write", "Glob", "Grep",
                    ):
                        fp = block.tool_input.get("file_path", "")
                        if fp and fp not in seen_files:
                            seen_files.add(fp)

                # Merge into existing assistant message or create new one
                # Claude streaming sends multiple assistant lines per turn
                if (
                    session.messages
                    and session.messages[-1].role == "assistant"
                ):
                    session.messages[-1].content_blocks.extend(blocks)
                else:
                    session.messages.append(Message(
                        role="assistant",
                        content_blocks=blocks,
                    ))

            # Skip "progress", "file-history-snapshot", etc.

    session.related_files = sorted(seen_files)
    return session
