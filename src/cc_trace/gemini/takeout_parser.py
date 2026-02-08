"""Parser for Gemini MyActivity JSON from Google Takeout.

Parses the 'My Activity.json' file exported from Google Takeout and
extracts user prompts with their corresponding Gemini responses.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPTED_PREFIX = "Prompted "


@dataclass
class TakeoutEntry:
    """A single Gemini interaction from Takeout data."""

    prompt_text: str
    response_html: str
    timestamp: str  # ISO 8601
    gem_name: str = ""
    attached_files: list[str] = field(default_factory=list)
    regenerated_responses: list[str] = field(default_factory=list)


def parse_takeout(path: Path) -> list[TakeoutEntry]:
    """Parse a Gemini MyActivity JSON file.

    Args:
        path: Path to the My Activity.json file.

    Returns:
        List of TakeoutEntry objects in chronological order (oldest first).
    """
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        logger.warning("Expected JSON array, got %s", type(data).__name__)
        return []

    entries: list[TakeoutEntry] = []

    for item in data:
        entry = _parse_entry(item)
        if entry is not None:
            entries.append(entry)

    # Takeout data is newest-first; reverse to chronological order
    entries.reverse()

    logger.info("Parsed %d entries from %s", len(entries), path)
    return entries


def _parse_entry(item: dict) -> TakeoutEntry | None:
    """Parse a single Takeout entry.

    Returns None for non-prompt entries (Created, Used, feedback, etc.)
    """
    title = item.get("title", "")

    # Only process "Prompted ..." entries
    if not title.startswith(PROMPTED_PREFIX):
        return None

    prompt_text = title[len(PROMPTED_PREFIX) :]
    timestamp = item.get("time", "")

    # Extract response HTML
    safe_html_items = item.get("safeHtmlItem", [])
    if safe_html_items and isinstance(safe_html_items, list):
        response_html = safe_html_items[0].get("html", "")
        # Additional responses are regenerations
        regenerated = [h.get("html", "") for h in safe_html_items[1:] if h.get("html")]
    else:
        response_html = ""
        regenerated = []

    # Extract metadata from subtitles
    gem_name = ""
    attached_files: list[str] = []
    subtitles = item.get("subtitles", [])

    for subtitle in subtitles:
        name = subtitle.get("name", "")

        # Check for Gem usage
        if " was used in this chat." in name:
            # Extract Gem name from "GemName was used in this chat. Manage your Gems."
            gem_name = name.split(" was used in this chat.")[0]
        # Check for attached files
        elif name.startswith("-  "):
            # File reference: "-  filename.png"
            attached_files.append(name[3:])

    # Also check imageFile field
    image_file = item.get("imageFile")
    if image_file and image_file not in attached_files:
        attached_files.append(image_file)

    return TakeoutEntry(
        prompt_text=prompt_text,
        response_html=response_html,
        timestamp=timestamp,
        gem_name=gem_name,
        attached_files=attached_files,
        regenerated_responses=regenerated,
    )
