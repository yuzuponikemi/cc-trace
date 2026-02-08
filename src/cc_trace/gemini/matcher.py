"""Match Takeout entries with crawled conversation structure.

Uses text prefix matching and temporal proximity to group
independent Takeout entries into conversations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from cc_trace.gemini.takeout_parser import TakeoutEntry
from cc_trace.gemini.transformer import Conversation

logger = logging.getLogger(__name__)

# Maximum time gap between prompts in the same conversation
DEFAULT_TIME_WINDOW_MINUTES = 30


@dataclass
class CrawledPrompt:
    """A prompt from browser crawling with conversation context."""

    conversation_id: str
    conversation_title: str
    text_preview: str  # First ~100 characters of the prompt
    order_in_conversation: int = 0


@dataclass
class CrawlCache:
    """Cache of crawled conversation structure."""

    conversations: dict[str, str] = field(default_factory=dict)  # id -> title
    prompts: list[CrawledPrompt] = field(default_factory=list)


def match_entries(
    entries: list[TakeoutEntry],
    crawl_cache: CrawlCache,
    time_window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
) -> tuple[list[Conversation], list[Conversation]]:
    """Match Takeout entries with crawled conversation structure.

    Args:
        entries: List of TakeoutEntry from Takeout parser.
        crawl_cache: CrawlCache from browser crawling.
        time_window_minutes: Max gap between prompts in same conversation.

    Returns:
        Tuple of (matched_conversations, unmatched_conversations).
        Unmatched conversations are grouped by temporal proximity.
    """
    if not entries:
        return [], []

    matched: list[Conversation] = []
    unmatched_entries: list[TakeoutEntry] = []

    # Build lookup index from crawl cache
    prompt_to_conv = _build_prompt_index(crawl_cache)

    # Track which entries are matched to which conversation
    conv_entries: dict[str, list[TakeoutEntry]] = {}

    for entry in entries:
        conv_id = _find_matching_conversation(entry, prompt_to_conv)

        if conv_id:
            if conv_id not in conv_entries:
                conv_entries[conv_id] = []
            conv_entries[conv_id].append(entry)
        else:
            unmatched_entries.append(entry)

    # Build matched conversations
    for conv_id, conv_ents in conv_entries.items():
        title = crawl_cache.conversations.get(conv_id, "Untitled")
        matched.append(
            Conversation(
                conversation_id=conv_id,
                title=title,
                entries=conv_ents,
            )
        )

    # Group unmatched entries by temporal proximity
    unmatched = _group_by_time(unmatched_entries, time_window_minutes)

    logger.info(
        "Matched %d conversations (%d entries), "
        "%d unmatched groups (%d entries)",
        len(matched),
        sum(len(c.entries) for c in matched),
        len(unmatched),
        len(unmatched_entries),
    )

    return matched, unmatched


def _build_prompt_index(crawl_cache: CrawlCache) -> dict[str, str]:
    """Build index mapping prompt prefix to conversation ID.

    Returns:
        Dict mapping normalized text prefix to conversation_id.
    """
    index: dict[str, str] = {}

    for prompt in crawl_cache.prompts:
        # Normalize: lowercase and strip whitespace
        key = _normalize_text(prompt.text_preview)
        if key:
            index[key] = prompt.conversation_id

    return index


def _normalize_text(text: str) -> str:
    """Normalize text for matching."""
    return text.strip().lower()


def _find_matching_conversation(
    entry: TakeoutEntry,
    prompt_index: dict[str, str],
) -> str | None:
    """Find matching conversation for a Takeout entry.

    Uses prefix matching: the crawled text_preview (~100 chars)
    should match the start of the full prompt_text.
    """
    entry_text = _normalize_text(entry.prompt_text)

    if not entry_text:
        return None

    # Try exact prefix match against all known prefixes
    for prefix, conv_id in prompt_index.items():
        if entry_text.startswith(prefix) or prefix.startswith(entry_text):
            return conv_id

    return None


def _group_by_time(
    entries: list[TakeoutEntry],
    window_minutes: int,
) -> list[Conversation]:
    """Group entries by temporal proximity.

    Entries within window_minutes of each other are grouped together.
    """
    if not entries:
        return []

    # Sort by timestamp
    sorted_entries = sorted(entries, key=lambda e: e.timestamp)

    groups: list[list[TakeoutEntry]] = []
    current_group: list[TakeoutEntry] = []
    last_time: datetime | None = None

    window = timedelta(minutes=window_minutes)

    for entry in sorted_entries:
        entry_time = _parse_timestamp(entry.timestamp)

        if entry_time is None:
            # Can't parse timestamp, treat as new group
            if current_group:
                groups.append(current_group)
            current_group = [entry]
            last_time = None
            continue

        if last_time is None or (entry_time - last_time) <= window:
            current_group.append(entry)
        else:
            if current_group:
                groups.append(current_group)
            current_group = [entry]

        last_time = entry_time

    if current_group:
        groups.append(current_group)

    # Convert groups to Conversations
    conversations: list[Conversation] = []
    for i, group in enumerate(groups):
        # Generate ID from first entry timestamp
        first_ts = group[0].timestamp[:10] if group[0].timestamp else "unknown"
        conv_id = f"unmatched-{first_ts}-{i:04d}"

        # Generate title from first prompt (truncated)
        first_prompt = group[0].prompt_text[:50]
        if len(group[0].prompt_text) > 50:
            first_prompt += "..."

        conversations.append(
            Conversation(
                conversation_id=conv_id,
                title=first_prompt,
                entries=group,
            )
        )

    return conversations


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse ISO 8601 timestamp."""
    if not ts:
        return None

    try:
        # Handle both formats: with and without milliseconds
        if "." in ts:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Failed to parse timestamp: %s", ts)
        return None


def make_unmatched_filename(conversation: Conversation, index: int) -> str:
    """Generate filename for unmatched conversation group.

    Format: GEM-{date}-unmatched-{index}.md
    """
    date_str = conversation.created_at[:10] if conversation.created_at else "unknown"
    return f"GEM-{date_str}-unmatched-{index:04d}.md"
