"""Tests for Gemini takeout parser."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cc_trace.gemini.takeout_parser import TakeoutEntry, parse_takeout


def _write_json(path: Path, data: list) -> None:
    """Write JSON data to file."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f)


def test_parse_empty_array() -> None:
    """Empty array returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "activity.json"
        _write_json(path, [])
        result = parse_takeout(path)
        assert result == []


def test_parse_single_prompt() -> None:
    """Single prompted entry is parsed correctly."""
    data = [
        {
            "header": "Gemini Apps",
            "title": "Prompted Hello, how are you?",
            "time": "2026-01-15T10:30:00.000Z",
            "products": ["Gemini Apps"],
            "activityControls": ["Gemini Apps Activity"],
            "safeHtmlItem": [{"html": "<p>I'm doing well, thank you!</p>"}],
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "activity.json"
        _write_json(path, data)
        result = parse_takeout(path)

        assert len(result) == 1
        entry = result[0]
        assert entry.prompt_text == "Hello, how are you?"
        assert entry.response_html == "<p>I'm doing well, thank you!</p>"
        assert entry.timestamp == "2026-01-15T10:30:00.000Z"
        assert entry.gem_name == ""
        assert entry.attached_files == []


def test_skip_non_prompted_entries() -> None:
    """Non-prompted entries are skipped."""
    data = [
        {
            "header": "Gemini Apps",
            "title": "Created a new canvas",
            "time": "2026-01-15T10:30:00.000Z",
            "products": ["Gemini Apps"],
        },
        {
            "header": "Gemini Apps",
            "title": "Gave feedback: Good response",
            "time": "2026-01-15T10:31:00.000Z",
            "products": ["Gemini Apps"],
        },
        {
            "header": "Gemini Apps",
            "title": "Prompted actual question",
            "time": "2026-01-15T10:32:00.000Z",
            "products": ["Gemini Apps"],
            "safeHtmlItem": [{"html": "<p>answer</p>"}],
        },
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "activity.json"
        _write_json(path, data)
        result = parse_takeout(path)

        assert len(result) == 1
        assert result[0].prompt_text == "actual question"


def test_chronological_order() -> None:
    """Entries are returned in chronological order (oldest first)."""
    # Takeout data is newest-first
    data = [
        {
            "title": "Prompted third",
            "time": "2026-01-15T12:00:00.000Z",
            "safeHtmlItem": [{"html": "<p>3</p>"}],
        },
        {
            "title": "Prompted second",
            "time": "2026-01-15T11:00:00.000Z",
            "safeHtmlItem": [{"html": "<p>2</p>"}],
        },
        {
            "title": "Prompted first",
            "time": "2026-01-15T10:00:00.000Z",
            "safeHtmlItem": [{"html": "<p>1</p>"}],
        },
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "activity.json"
        _write_json(path, data)
        result = parse_takeout(path)

        assert len(result) == 3
        assert result[0].prompt_text == "first"
        assert result[1].prompt_text == "second"
        assert result[2].prompt_text == "third"


def test_gem_usage() -> None:
    """Gem name is extracted from subtitles."""
    data = [
        {
            "title": "Prompted test with gem",
            "time": "2026-01-15T10:00:00.000Z",
            "safeHtmlItem": [{"html": "<p>response</p>"}],
            "subtitles": [
                {
                    "name": "RonbunOchiAI3 was used in this chat. Manage your Gems.",
                    "url": "https://gemini.google.com/gems/...",
                }
            ],
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "activity.json"
        _write_json(path, data)
        result = parse_takeout(path)

        assert len(result) == 1
        assert result[0].gem_name == "RonbunOchiAI3"


def test_attached_files() -> None:
    """Attached files are extracted from subtitles and imageFile."""
    data = [
        {
            "title": "Prompted image test",
            "time": "2026-01-15T10:00:00.000Z",
            "safeHtmlItem": [{"html": "<p>I see the image</p>"}],
            "subtitles": [
                {"name": "Attached 1 file."},
                {"name": "-  image_89b1bd.png", "url": "image_89b1bd-1e9873211d1a6157.png"},
            ],
            "imageFile": "image_89b1bd-1e9873211d1a6157.png",
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "activity.json"
        _write_json(path, data)
        result = parse_takeout(path)

        assert len(result) == 1
        # Both subtitle file and imageFile should be captured (but not duplicated)
        assert "image_89b1bd.png" in result[0].attached_files
        assert "image_89b1bd-1e9873211d1a6157.png" in result[0].attached_files


def test_regenerated_responses() -> None:
    """Multiple safeHtmlItem entries indicate regenerated responses."""
    data = [
        {
            "title": "Prompted regenerate test",
            "time": "2026-01-15T10:00:00.000Z",
            "safeHtmlItem": [
                {"html": "<p>First response</p>"},
                {"html": "<p>Second response (regenerated)</p>"},
                {"html": "<p>Third response</p>"},
            ],
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "activity.json"
        _write_json(path, data)
        result = parse_takeout(path)

        assert len(result) == 1
        entry = result[0]
        assert entry.response_html == "<p>First response</p>"
        assert len(entry.regenerated_responses) == 2
        assert entry.regenerated_responses[0] == "<p>Second response (regenerated)</p>"
        assert entry.regenerated_responses[1] == "<p>Third response</p>"


def test_no_response() -> None:
    """Entry without safeHtmlItem has empty response."""
    data = [
        {
            "title": "Prompted no response",
            "time": "2026-01-15T10:00:00.000Z",
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "activity.json"
        _write_json(path, data)
        result = parse_takeout(path)

        assert len(result) == 1
        assert result[0].prompt_text == "no response"
        assert result[0].response_html == ""


def test_invalid_json_structure() -> None:
    """Non-array JSON returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "activity.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump({"not": "an array"}, f)
        result = parse_takeout(path)
        assert result == []
