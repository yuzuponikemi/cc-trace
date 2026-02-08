"""Tests for Gemini matcher (Takeout entries + crawl cache matching)."""

from __future__ import annotations

from cc_trace.gemini.matcher import (
    CrawlCache,
    CrawledPrompt,
    match_entries,
    make_unmatched_filename,
)
from cc_trace.gemini.takeout_parser import TakeoutEntry


def _make_entry(
    prompt: str,
    timestamp: str = "2026-01-15T10:00:00.000Z",
    response: str = "<p>Response</p>",
) -> TakeoutEntry:
    """Helper to create TakeoutEntry for testing."""
    return TakeoutEntry(
        prompt_text=prompt,
        response_html=response,
        timestamp=timestamp,
    )


def _make_crawl_cache(
    conversations: dict[str, str],
    prompts: list[tuple[str, str, str]],  # (conv_id, title, text_preview)
) -> CrawlCache:
    """Helper to create CrawlCache for testing."""
    cache = CrawlCache(conversations=conversations)
    for conv_id, title, text_preview in prompts:
        cache.prompts.append(
            CrawledPrompt(
                conversation_id=conv_id,
                conversation_title=title,
                text_preview=text_preview,
            )
        )
    return cache


def test_empty_entries() -> None:
    """Empty entries returns empty results."""
    cache = CrawlCache()
    matched, unmatched = match_entries([], cache)
    assert matched == []
    assert unmatched == []


def test_no_crawl_cache() -> None:
    """Entries without crawl cache become unmatched."""
    entries = [_make_entry("Hello world")]
    cache = CrawlCache()

    matched, unmatched = match_entries(entries, cache)

    assert len(matched) == 0
    assert len(unmatched) == 1
    assert unmatched[0].entries[0].prompt_text == "Hello world"


def test_exact_match() -> None:
    """Entry matching crawl cache exactly is matched."""
    entries = [_make_entry("What is Python?")]
    cache = _make_crawl_cache(
        {"conv1": "Python discussion"},
        [("conv1", "Python discussion", "what is python?")],
    )

    matched, unmatched = match_entries(entries, cache)

    assert len(matched) == 1
    assert len(unmatched) == 0
    assert matched[0].conversation_id == "conv1"
    assert matched[0].title == "Python discussion"
    assert len(matched[0].entries) == 1


def test_prefix_match() -> None:
    """Entry matching crawl cache prefix is matched."""
    # Full prompt text in Takeout
    entries = [
        _make_entry("This is a very long prompt that continues for many words")
    ]
    # Truncated preview from crawling (first ~100 chars)
    cache = _make_crawl_cache(
        {"conv1": "Long prompt"},
        [("conv1", "Long prompt", "this is a very long prompt that continues")],
    )

    matched, unmatched = match_entries(entries, cache)

    assert len(matched) == 1
    assert matched[0].conversation_id == "conv1"


def test_multiple_entries_same_conversation() -> None:
    """Multiple entries matching same conversation are grouped."""
    entries = [
        _make_entry("First question about Python", "2026-01-15T10:00:00.000Z"),
        _make_entry("Second question about Python", "2026-01-15T10:05:00.000Z"),
    ]
    cache = _make_crawl_cache(
        {"conv1": "Python questions"},
        [
            ("conv1", "Python questions", "first question about python"),
            ("conv1", "Python questions", "second question about python"),
        ],
    )

    matched, unmatched = match_entries(entries, cache)

    assert len(matched) == 1
    assert len(matched[0].entries) == 2


def test_multiple_conversations() -> None:
    """Entries are correctly distributed across conversations."""
    entries = [
        _make_entry("Python question"),
        _make_entry("JavaScript question"),
    ]
    cache = _make_crawl_cache(
        {"conv1": "Python", "conv2": "JavaScript"},
        [
            ("conv1", "Python", "python question"),
            ("conv2", "JavaScript", "javascript question"),
        ],
    )

    matched, unmatched = match_entries(entries, cache)

    assert len(matched) == 2
    assert len(unmatched) == 0

    conv_ids = {c.conversation_id for c in matched}
    assert conv_ids == {"conv1", "conv2"}


def test_unmatched_temporal_grouping() -> None:
    """Unmatched entries within time window are grouped together."""
    entries = [
        _make_entry("Question A", "2026-01-15T10:00:00.000Z"),
        _make_entry("Question B", "2026-01-15T10:05:00.000Z"),  # 5 min later
        _make_entry("Question C", "2026-01-15T10:10:00.000Z"),  # 10 min later
    ]
    cache = CrawlCache()  # No matches

    # Default window is 30 minutes, so all should be in one group
    matched, unmatched = match_entries(entries, cache)

    assert len(matched) == 0
    assert len(unmatched) == 1
    assert len(unmatched[0].entries) == 3


def test_unmatched_separate_groups() -> None:
    """Unmatched entries beyond time window are in separate groups."""
    entries = [
        _make_entry("Morning question", "2026-01-15T10:00:00.000Z"),
        _make_entry("Afternoon question", "2026-01-15T14:00:00.000Z"),  # 4 hours later
    ]
    cache = CrawlCache()

    matched, unmatched = match_entries(entries, cache, time_window_minutes=30)

    assert len(matched) == 0
    assert len(unmatched) == 2
    assert unmatched[0].entries[0].prompt_text == "Morning question"
    assert unmatched[1].entries[0].prompt_text == "Afternoon question"


def test_mixed_matched_and_unmatched() -> None:
    """Some entries match, others don't."""
    entries = [
        _make_entry("Known question"),
        _make_entry("Unknown question"),
    ]
    cache = _make_crawl_cache(
        {"conv1": "Known"},
        [("conv1", "Known", "known question")],
    )

    matched, unmatched = match_entries(entries, cache)

    assert len(matched) == 1
    assert len(unmatched) == 1
    assert matched[0].entries[0].prompt_text == "Known question"
    assert unmatched[0].entries[0].prompt_text == "Unknown question"


def test_case_insensitive_matching() -> None:
    """Matching is case-insensitive."""
    entries = [_make_entry("WHAT IS PYTHON?")]
    cache = _make_crawl_cache(
        {"conv1": "Python"},
        [("conv1", "Python", "what is python?")],
    )

    matched, unmatched = match_entries(entries, cache)

    assert len(matched) == 1
    assert len(unmatched) == 0


def test_unmatched_filename() -> None:
    """Unmatched filename is generated correctly."""
    from cc_trace.gemini.transformer import Conversation

    conv = Conversation(
        conversation_id="unmatched-2026-01-15-0000",
        title="Some prompt...",
        entries=[_make_entry("Test", "2026-01-15T10:00:00.000Z")],
    )

    filename = make_unmatched_filename(conv, 0)
    assert filename == "GEM-2026-01-15-unmatched-0000.md"


def test_unmatched_title_from_first_prompt() -> None:
    """Unmatched conversation title is derived from first prompt."""
    entries = [_make_entry("This is a very long prompt that should be truncated")]
    cache = CrawlCache()

    matched, unmatched = match_entries(entries, cache)

    assert len(unmatched) == 1
    assert unmatched[0].title.startswith("This is a very long prompt")
    assert unmatched[0].title.endswith("...")


def test_short_prompt_no_truncation() -> None:
    """Short prompts are not truncated in unmatched title."""
    entries = [_make_entry("Short")]
    cache = CrawlCache()

    matched, unmatched = match_entries(entries, cache)

    assert unmatched[0].title == "Short"
