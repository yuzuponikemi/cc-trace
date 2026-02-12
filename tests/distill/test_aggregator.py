"""Tests for distill aggregator."""

from __future__ import annotations

from cc_trace.distill.aggregator import group_by_date
from cc_trace.gemini.takeout_parser import TakeoutEntry


def _entry(prompt: str, timestamp: str, gem_name: str = "") -> TakeoutEntry:
    return TakeoutEntry(
        prompt_text=prompt,
        response_html="",
        timestamp=timestamp,
        gem_name=gem_name,
    )


def test_empty_entries() -> None:
    result = group_by_date([])
    assert result == []


def test_single_day() -> None:
    entries = [
        _entry("hello", "2026-02-11T10:00:00.000Z"),
        _entry("world", "2026-02-11T14:00:00.000Z"),
    ]
    result = group_by_date(entries)
    assert len(result) == 1
    assert result[0].date == "2026-02-11"
    assert result[0].prompts == ["hello", "world"]
    assert result[0].prompt_count == 2
    assert result[0].gem_names == []


def test_multiple_days_sorted() -> None:
    entries = [
        _entry("a", "2026-02-10T10:00:00.000Z"),
        _entry("b", "2026-02-12T10:00:00.000Z"),
        _entry("c", "2026-02-11T10:00:00.000Z"),
    ]
    result = group_by_date(entries)
    assert len(result) == 3
    assert result[0].date == "2026-02-10"
    assert result[1].date == "2026-02-11"
    assert result[2].date == "2026-02-12"


def test_date_from_filter() -> None:
    entries = [
        _entry("old", "2026-02-09T10:00:00.000Z"),
        _entry("new", "2026-02-11T10:00:00.000Z"),
    ]
    result = group_by_date(entries, date_from="2026-02-10")
    assert len(result) == 1
    assert result[0].date == "2026-02-11"


def test_date_to_filter() -> None:
    entries = [
        _entry("old", "2026-02-09T10:00:00.000Z"),
        _entry("new", "2026-02-11T10:00:00.000Z"),
    ]
    result = group_by_date(entries, date_to="2026-02-10")
    assert len(result) == 1
    assert result[0].date == "2026-02-09"


def test_date_range_filter() -> None:
    entries = [
        _entry("a", "2026-02-08T10:00:00.000Z"),
        _entry("b", "2026-02-09T10:00:00.000Z"),
        _entry("c", "2026-02-10T10:00:00.000Z"),
        _entry("d", "2026-02-11T10:00:00.000Z"),
    ]
    result = group_by_date(entries, date_from="2026-02-09", date_to="2026-02-10")
    assert len(result) == 2
    assert result[0].date == "2026-02-09"
    assert result[1].date == "2026-02-10"


def test_gem_names_collected() -> None:
    entries = [
        _entry("a", "2026-02-11T10:00:00.000Z", gem_name="GemA"),
        _entry("b", "2026-02-11T11:00:00.000Z", gem_name="GemB"),
        _entry("c", "2026-02-11T12:00:00.000Z", gem_name="GemA"),
    ]
    result = group_by_date(entries)
    assert len(result) == 1
    assert result[0].gem_names == ["GemA", "GemB"]


def test_empty_timestamp_skipped() -> None:
    entries = [
        _entry("a", ""),
        _entry("b", "2026-02-11T10:00:00.000Z"),
    ]
    result = group_by_date(entries)
    assert len(result) == 1
    assert result[0].prompts == ["b"]


def test_date_from_inclusive() -> None:
    entries = [_entry("a", "2026-02-10T10:00:00.000Z")]
    result = group_by_date(entries, date_from="2026-02-10")
    assert len(result) == 1


def test_date_to_inclusive() -> None:
    entries = [_entry("a", "2026-02-10T10:00:00.000Z")]
    result = group_by_date(entries, date_to="2026-02-10")
    assert len(result) == 1
