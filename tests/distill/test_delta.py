"""Tests for delta computation."""

from __future__ import annotations

from cc_trace.distill.delta import compute_delta
from cc_trace.distill.models import Distillation


def _distill(
    date: str,
    core_topics: list[str] | None = None,
    interests: list[str] | None = None,
    energy_level: str = "",
    domain_tags: list[str] | None = None,
) -> Distillation:
    return Distillation(
        date=date,
        core_topics=core_topics or [],
        interests=interests or [],
        energy_level=energy_level,
        domain_tags=domain_tags or [],
    )


def test_identical_distillations() -> None:
    prev = _distill("2026-02-10", core_topics=["A", "B"], interests=["X"])
    curr = _distill("2026-02-11", core_topics=["A", "B"], interests=["X"])
    delta = compute_delta(curr, prev)
    assert delta.new_topics == []
    assert delta.faded_topics == []
    assert delta.shifted_topics == []
    assert delta.mood_shift == ""


def test_new_topics() -> None:
    prev = _distill("2026-02-10", core_topics=["A"])
    curr = _distill("2026-02-11", core_topics=["A", "B", "C"])
    delta = compute_delta(curr, prev)
    assert delta.new_topics == ["B", "C"]
    assert delta.faded_topics == []


def test_faded_topics() -> None:
    prev = _distill("2026-02-10", core_topics=["A", "B", "C"])
    curr = _distill("2026-02-11", core_topics=["A"])
    delta = compute_delta(curr, prev)
    assert delta.faded_topics == ["B", "C"]
    assert delta.new_topics == []


def test_topic_promoted_to_core() -> None:
    prev = _distill("2026-02-10", core_topics=["A"], interests=["B"])
    curr = _distill("2026-02-11", core_topics=["A", "B"], interests=[])
    delta = compute_delta(curr, prev)
    assert any("B: interest → core" in s for s in delta.shifted_topics)
    assert delta.faded_topics == []


def test_topic_demoted_to_interest() -> None:
    prev = _distill("2026-02-10", core_topics=["A", "B"], interests=[])
    curr = _distill("2026-02-11", core_topics=["A"], interests=["B"])
    delta = compute_delta(curr, prev)
    assert any("B: core → interest" in s for s in delta.shifted_topics)
    assert delta.faded_topics == []


def test_energy_shift() -> None:
    prev = _distill("2026-02-10", energy_level="low")
    curr = _distill("2026-02-11", energy_level="high")
    delta = compute_delta(curr, prev)
    assert delta.mood_shift == "low → high"


def test_no_energy_shift_when_same() -> None:
    prev = _distill("2026-02-10", energy_level="medium")
    curr = _distill("2026-02-11", energy_level="medium")
    delta = compute_delta(curr, prev)
    assert delta.mood_shift == ""


def test_no_energy_shift_when_missing() -> None:
    prev = _distill("2026-02-10", energy_level="")
    curr = _distill("2026-02-11", energy_level="high")
    delta = compute_delta(curr, prev)
    assert delta.mood_shift == ""


def test_domain_changes() -> None:
    prev = _distill("2026-02-10", domain_tags=["engineer", "philosopher"])
    curr = _distill("2026-02-11", domain_tags=["engineer", "creative"])
    delta = compute_delta(curr, prev)
    assert delta.new_domains == ["creative"]
    assert delta.lost_domains == ["philosopher"]


def test_dates_preserved() -> None:
    prev = _distill("2026-02-10")
    curr = _distill("2026-02-11")
    delta = compute_delta(curr, prev)
    assert delta.current_date == "2026-02-11"
    assert delta.previous_date == "2026-02-10"


def test_topic_in_prev_interest_not_new() -> None:
    """A topic that was in previous interests is not counted as new."""
    prev = _distill("2026-02-10", core_topics=[], interests=["B"])
    curr = _distill("2026-02-11", core_topics=["B"], interests=[])
    delta = compute_delta(curr, prev)
    assert delta.new_topics == []
