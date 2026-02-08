"""Sync orchestration for Gemini conversations.

Combines Takeout data with crawl cache, handles deduplication,
and writes Obsidian Markdown files.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from cc_trace.gemini.matcher import CrawlCache, CrawledPrompt, match_entries, make_unmatched_filename
from cc_trace.gemini.takeout_parser import parse_takeout
from cc_trace.gemini.transformer import (
    Conversation,
    make_output_filename,
    transform_conversation,
)

if TYPE_CHECKING:
    from cc_trace.config import Config

logger = logging.getLogger(__name__)


def sync(
    config: Config,
    takeout_path: Path,
    inbox_override: Path | None = None,
) -> int:
    """Sync Gemini conversations from Takeout to Obsidian.

    Args:
        config: Application configuration.
        takeout_path: Path to My Activity.json from Takeout.
        inbox_override: Optional override for output directory.

    Returns:
        Number of files written.
    """
    inbox = inbox_override or config.obsidian_inbox
    inbox.mkdir(parents=True, exist_ok=True)

    # Load state for deduplication
    state = _load_state(config.gemini.state_file)

    # Parse Takeout data
    logger.info("Parsing Takeout file: %s", takeout_path)
    entries = parse_takeout(takeout_path)

    if not entries:
        logger.warning("No entries found in Takeout file")
        return 0

    # Load crawl cache if available
    crawl_cache = _load_crawl_cache(config.gemini.crawl_cache)

    # Match entries with crawled conversation structure
    matched, unmatched = match_entries(entries, crawl_cache)

    # Process all conversations
    written = 0

    for conv in matched:
        if _write_conversation(conv, inbox, state):
            written += 1

    for i, conv in enumerate(unmatched):
        if _write_unmatched_conversation(conv, i, inbox, state):
            written += 1

    # Save updated state
    _save_state(config.gemini.state_file, state)

    logger.info(
        "Sync complete: %d files written (%d matched, %d unmatched groups)",
        written,
        len(matched),
        len(unmatched),
    )

    return written


def _write_conversation(
    conv: Conversation,
    inbox: Path,
    state: dict,
) -> bool:
    """Write a matched conversation to file.

    Returns True if file was written, False if skipped (duplicate).
    """
    filename = make_output_filename(conv)
    return _write_file(conv, filename, inbox, state)


def _write_unmatched_conversation(
    conv: Conversation,
    index: int,
    inbox: Path,
    state: dict,
) -> bool:
    """Write an unmatched conversation to file.

    Returns True if file was written, False if skipped (duplicate).
    """
    filename = make_unmatched_filename(conv, index)
    return _write_file(conv, filename, inbox, state)


def _write_file(
    conv: Conversation,
    filename: str,
    inbox: Path,
    state: dict,
) -> bool:
    """Write conversation to file with deduplication.

    Returns True if file was written, False if skipped.
    """
    content = transform_conversation(conv)
    content_hash = _compute_hash(content)

    # Check if already processed
    if conv.conversation_id in state:
        if state[conv.conversation_id]["hash"] == content_hash:
            logger.debug("Skipping duplicate: %s", filename)
            return False

    # Write file
    output_path = inbox / filename
    output_path.write_text(content, encoding="utf-8")
    logger.info("Wrote: %s", output_path)

    # Update state
    state[conv.conversation_id] = {
        "hash": content_hash,
        "filename": filename,
    }

    return True


def _compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_state(state_file: Path) -> dict:
    """Load sync state from file."""
    if state_file.exists():
        try:
            with state_file.open(encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load state file: %s", e)

    return {}


def _save_state(state_file: Path, state: dict) -> None:
    """Save sync state to file."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _load_crawl_cache(cache_file: Path) -> CrawlCache:
    """Load crawl cache from file."""
    if not cache_file.exists():
        logger.info("No crawl cache found at %s", cache_file)
        return CrawlCache()

    try:
        with cache_file.open(encoding="utf-8") as f:
            data = json.load(f)

        cache = CrawlCache(
            conversations=data.get("conversations", {}),
        )

        for prompt_data in data.get("prompts", []):
            cache.prompts.append(
                CrawledPrompt(
                    conversation_id=prompt_data.get("conversation_id", ""),
                    conversation_title=prompt_data.get("conversation_title", ""),
                    text_preview=prompt_data.get("text_preview", ""),
                    order_in_conversation=prompt_data.get("order_in_conversation", 0),
                )
            )

        logger.info(
            "Loaded crawl cache: %d conversations, %d prompts",
            len(cache.conversations),
            len(cache.prompts),
        )
        return cache

    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load crawl cache: %s", e)
        return CrawlCache()


def save_crawl_cache(cache_file: Path, cache: CrawlCache) -> None:
    """Save crawl cache to file."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "conversations": cache.conversations,
        "prompts": [
            {
                "conversation_id": p.conversation_id,
                "conversation_title": p.conversation_title,
                "text_preview": p.text_preview,
                "order_in_conversation": p.order_in_conversation,
            }
            for p in cache.prompts
        ],
    }

    with cache_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Saved crawl cache: %d conversations", len(cache.conversations))
