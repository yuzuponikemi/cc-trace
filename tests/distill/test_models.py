"""Tests for distill data models."""

from __future__ import annotations

from cc_trace.distill.models import (
    DayPrompts,
    Delta,
    Distillation,
    DistillationResult,
)


def test_day_prompts_defaults() -> None:
    dp = DayPrompts(date="2026-02-11")
    assert dp.date == "2026-02-11"
    assert dp.prompts == []
    assert dp.prompt_count == 0
    assert dp.gem_names == []


def test_distillation_defaults() -> None:
    d = Distillation(date="2026-02-11")
    assert d.core_topics == []
    assert d.interests == []
    assert d.mood_tension == ""
    assert d.energy_level == ""
    assert d.key_questions == []
    assert d.domain_tags == []
    assert d.prompt_count == 0
    assert d.model == ""


def test_delta_defaults() -> None:
    d = Delta(current_date="2026-02-11", previous_date="2026-02-10")
    assert d.new_topics == []
    assert d.shifted_topics == []
    assert d.faded_topics == []
    assert d.mood_shift == ""
    assert d.new_domains == []
    assert d.lost_domains == []


def test_distillation_result_without_delta() -> None:
    distillation = Distillation(date="2026-02-11")
    result = DistillationResult(distillation=distillation)
    assert result.delta is None


def test_distillation_result_with_delta() -> None:
    distillation = Distillation(date="2026-02-11")
    delta = Delta(current_date="2026-02-11", previous_date="2026-02-10")
    result = DistillationResult(distillation=distillation, delta=delta)
    assert result.delta is not None
    assert result.delta.current_date == "2026-02-11"
