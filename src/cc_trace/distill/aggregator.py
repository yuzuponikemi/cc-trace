"""Aggregate TakeoutEntry list into per-day prompt groups."""

from __future__ import annotations

import logging
from collections import defaultdict

from cc_trace.distill.models import DayPrompts
from cc_trace.gemini.takeout_parser import TakeoutEntry

logger = logging.getLogger(__name__)


def group_by_date(
    entries: list[TakeoutEntry],
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[DayPrompts]:
    """Group TakeoutEntry list by date.

    Args:
        entries: Chronologically ordered TakeoutEntry list.
        date_from: Inclusive start date (YYYY-MM-DD). None = no lower bound.
        date_to: Inclusive end date (YYYY-MM-DD). None = no upper bound.

    Returns:
        List of DayPrompts sorted by date ascending.
    """
    by_date: dict[str, dict] = defaultdict(lambda: {"prompts": [], "gems": set()})

    for entry in entries:
        date = _extract_date(entry.timestamp)
        if not date:
            continue

        if date_from and date < date_from:
            continue
        if date_to and date > date_to:
            continue

        by_date[date]["prompts"].append(entry.prompt_text)
        if entry.gem_name:
            by_date[date]["gems"].add(entry.gem_name)

    result = []
    for date in sorted(by_date):
        data = by_date[date]
        prompts = data["prompts"]
        result.append(
            DayPrompts(
                date=date,
                prompts=prompts,
                prompt_count=len(prompts),
                gem_names=sorted(data["gems"]),
            )
        )

    logger.info("Grouped %d entries into %d day(s)", len(entries), len(result))
    return result


def _extract_date(timestamp: str) -> str:
    """Extract YYYY-MM-DD from ISO 8601 timestamp."""
    if not timestamp:
        return ""
    # Handles both "2026-02-11T10:00:00.000Z" and "2026-02-11"
    return timestamp[:10]
