"""Tests for Gemini sync orchestration."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from cc_trace.gemini.sync import (
    _compute_hash,
    _load_crawl_cache,
    _load_state,
    _save_state,
    save_crawl_cache,
    sync,
)
from cc_trace.gemini.matcher import CrawlCache, CrawledPrompt


@dataclass
class MockGeminiConfig:
    """Mock Gemini config for testing."""

    browser_state: Path = field(default_factory=lambda: Path("/tmp/browser.json"))
    crawl_cache: Path = field(default_factory=lambda: Path("/tmp/crawl.json"))
    state_file: Path = field(default_factory=lambda: Path("/tmp/state.json"))


@dataclass
class MockConfig:
    """Mock config for testing."""

    obsidian_inbox: Path = field(default_factory=lambda: Path("/tmp/inbox"))
    gemini: MockGeminiConfig = field(default_factory=MockGeminiConfig)


def _write_takeout(path: Path, entries: list[dict]) -> None:
    """Write Takeout JSON file."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(entries, f)


def test_sync_empty_takeout() -> None:
    """Empty Takeout file returns 0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        takeout = tmppath / "activity.json"
        inbox = tmppath / "inbox"
        state_file = tmppath / "state.json"
        crawl_cache = tmppath / "crawl.json"

        _write_takeout(takeout, [])

        config = MockConfig(
            obsidian_inbox=inbox,
            gemini=MockGeminiConfig(
                state_file=state_file,
                crawl_cache=crawl_cache,
            ),
        )

        result = sync(config, takeout)
        assert result == 0


def test_sync_single_entry() -> None:
    """Single entry creates one file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        takeout = tmppath / "activity.json"
        inbox = tmppath / "inbox"
        state_file = tmppath / "state.json"
        crawl_cache = tmppath / "crawl.json"

        _write_takeout(
            takeout,
            [
                {
                    "title": "Prompted Hello world",
                    "time": "2026-01-15T10:00:00.000Z",
                    "safeHtmlItem": [{"html": "<p>Hi there!</p>"}],
                }
            ],
        )

        config = MockConfig(
            obsidian_inbox=inbox,
            gemini=MockGeminiConfig(
                state_file=state_file,
                crawl_cache=crawl_cache,
            ),
        )

        result = sync(config, takeout)
        assert result == 1

        # Check file exists
        files = list(inbox.glob("*.md"))
        assert len(files) == 1
        assert files[0].name.startswith("GEM-2026-01-15-")


def test_sync_deduplication() -> None:
    """Same content is not written twice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        takeout = tmppath / "activity.json"
        inbox = tmppath / "inbox"
        state_file = tmppath / "state.json"
        crawl_cache = tmppath / "crawl.json"

        _write_takeout(
            takeout,
            [
                {
                    "title": "Prompted Test",
                    "time": "2026-01-15T10:00:00.000Z",
                    "safeHtmlItem": [{"html": "<p>Answer</p>"}],
                }
            ],
        )

        config = MockConfig(
            obsidian_inbox=inbox,
            gemini=MockGeminiConfig(
                state_file=state_file,
                crawl_cache=crawl_cache,
            ),
        )

        # First sync
        result1 = sync(config, takeout)
        assert result1 == 1

        # Second sync - should skip duplicate
        result2 = sync(config, takeout)
        assert result2 == 0


def test_sync_with_crawl_cache() -> None:
    """Entries matching crawl cache use conversation info."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        takeout = tmppath / "activity.json"
        inbox = tmppath / "inbox"
        state_file = tmppath / "state.json"
        crawl_cache = tmppath / "crawl.json"

        _write_takeout(
            takeout,
            [
                {
                    "title": "Prompted What is Python?",
                    "time": "2026-01-15T10:00:00.000Z",
                    "safeHtmlItem": [{"html": "<p>Python is...</p>"}],
                }
            ],
        )

        # Write crawl cache
        cache_data = {
            "conversations": {"conv123": "Python Tutorial"},
            "prompts": [
                {
                    "conversation_id": "conv123",
                    "conversation_title": "Python Tutorial",
                    "text_preview": "what is python?",
                    "order_in_conversation": 0,
                }
            ],
        }
        with crawl_cache.open("w") as f:
            json.dump(cache_data, f)

        config = MockConfig(
            obsidian_inbox=inbox,
            gemini=MockGeminiConfig(
                state_file=state_file,
                crawl_cache=crawl_cache,
            ),
        )

        result = sync(config, takeout)
        assert result == 1

        # Check file uses conversation ID
        files = list(inbox.glob("*.md"))
        assert len(files) == 1
        assert "conv123" in files[0].name


def test_sync_inbox_override() -> None:
    """Inbox override is respected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        takeout = tmppath / "activity.json"
        inbox = tmppath / "inbox"
        override_inbox = tmppath / "custom_inbox"
        state_file = tmppath / "state.json"
        crawl_cache = tmppath / "crawl.json"

        _write_takeout(
            takeout,
            [
                {
                    "title": "Prompted Test",
                    "time": "2026-01-15T10:00:00.000Z",
                    "safeHtmlItem": [{"html": "<p>Answer</p>"}],
                }
            ],
        )

        config = MockConfig(
            obsidian_inbox=inbox,
            gemini=MockGeminiConfig(
                state_file=state_file,
                crawl_cache=crawl_cache,
            ),
        )

        result = sync(config, takeout, inbox_override=override_inbox)
        assert result == 1

        # Check file is in override location
        assert not inbox.exists() or len(list(inbox.glob("*.md"))) == 0
        assert len(list(override_inbox.glob("*.md"))) == 1


# --- State and cache tests ---


def test_load_state_nonexistent() -> None:
    """Missing state file returns empty dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "nonexistent.json"
        result = _load_state(state_file)
        assert result == {}


def test_load_save_state() -> None:
    """State is saved and loaded correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        state = {"conv1": {"hash": "abc123", "filename": "file.md"}}

        _save_state(state_file, state)
        loaded = _load_state(state_file)

        assert loaded == state


def test_load_crawl_cache_nonexistent() -> None:
    """Missing crawl cache returns empty cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "nonexistent.json"
        result = _load_crawl_cache(cache_file)
        assert result.conversations == {}
        assert result.prompts == []


def test_save_load_crawl_cache() -> None:
    """Crawl cache is saved and loaded correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "cache.json"

        cache = CrawlCache(
            conversations={"conv1": "Title 1", "conv2": "Title 2"},
            prompts=[
                CrawledPrompt(
                    conversation_id="conv1",
                    conversation_title="Title 1",
                    text_preview="hello world",
                    order_in_conversation=0,
                ),
            ],
        )

        save_crawl_cache(cache_file, cache)
        loaded = _load_crawl_cache(cache_file)

        assert loaded.conversations == cache.conversations
        assert len(loaded.prompts) == 1
        assert loaded.prompts[0].text_preview == "hello world"


def test_compute_hash() -> None:
    """Hash computation is consistent."""
    content = "Hello, world!"
    hash1 = _compute_hash(content)
    hash2 = _compute_hash(content)
    assert hash1 == hash2

    # Different content has different hash
    hash3 = _compute_hash("Different content")
    assert hash1 != hash3


def test_sync_creates_state_directory() -> None:
    """Sync creates state file directory if needed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        takeout = tmppath / "activity.json"
        inbox = tmppath / "inbox"
        state_file = tmppath / "nested" / "dir" / "state.json"
        crawl_cache = tmppath / "crawl.json"

        _write_takeout(
            takeout,
            [
                {
                    "title": "Prompted Test",
                    "time": "2026-01-15T10:00:00.000Z",
                    "safeHtmlItem": [{"html": "<p>Answer</p>"}],
                }
            ],
        )

        config = MockConfig(
            obsidian_inbox=inbox,
            gemini=MockGeminiConfig(
                state_file=state_file,
                crawl_cache=crawl_cache,
            ),
        )

        result = sync(config, takeout)
        assert result == 1
        assert state_file.exists()
