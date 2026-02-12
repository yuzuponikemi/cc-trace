"""Tests for Markdown formatter."""

from __future__ import annotations

from cc_trace.distill.formatter import format_distillation
from cc_trace.distill.models import Delta, Distillation, DistillationResult


def test_basic_output() -> None:
    d = Distillation(
        date="2026-02-11",
        core_topics=["Python", "テスト"],
        interests=["プログラミング"],
        mood_tension="集中モード",
        energy_level="high",
        key_questions=["良いテストとは?"],
        domain_tags=["engineer"],
        prompt_count=10,
        model="gemma3",
    )
    result = DistillationResult(distillation=d)
    md = format_distillation(result)

    # Frontmatter
    assert "---" in md
    assert "created: 2026-02-11" in md
    assert "tags: [log/distill, type/self_observation]" in md
    assert "status: auto_generated" in md
    assert "source: gemini_distill" in md
    assert "prompt_count: 10" in md
    assert "model: gemma3" in md
    assert "energy: high" in md
    assert "domains: [engineer]" in md

    # Content
    assert "# Self-Distillation: 2026-02-11" in md
    assert "## Core Topics" in md
    assert "- Python" in md
    assert "- テスト" in md
    assert "## Interests" in md
    assert "- プログラミング" in md
    assert "## Mood & Tension" in md
    assert "集中モード" in md
    assert "## Key Questions" in md
    assert "- 良いテストとは?" in md
    assert "## Domain Tags" in md
    assert "engineer" in md


def test_no_delta() -> None:
    d = Distillation(date="2026-02-11", prompt_count=1, model="gemma3")
    result = DistillationResult(distillation=d)
    md = format_distillation(result)
    assert "## Delta" not in md


def test_with_delta() -> None:
    d = Distillation(date="2026-02-11", prompt_count=1, model="gemma3")
    delta = Delta(
        current_date="2026-02-11",
        previous_date="2026-02-10",
        new_topics=["新しいトピック"],
        shifted_topics=["X: interest → core"],
        faded_topics=["古いトピック"],
        mood_shift="low → high",
        new_domains=["creative"],
        lost_domains=["philosopher"],
    )
    result = DistillationResult(distillation=d, delta=delta)
    md = format_distillation(result)

    assert "## Delta (from 2026-02-10)" in md
    assert "### New" in md
    assert "- 新しいトピック" in md
    assert "### Shifted" in md
    assert "- X: interest → core" in md
    assert "### Faded" in md
    assert "- 古いトピック" in md
    assert "### Energy Shift" in md
    assert "low → high" in md
    assert "### New Domains" in md
    assert "creative" in md
    assert "### Lost Domains" in md
    assert "philosopher" in md


def test_empty_distillation() -> None:
    d = Distillation(date="2026-02-11", prompt_count=0, model="gemma3")
    result = DistillationResult(distillation=d)
    md = format_distillation(result)

    assert "- (none)" in md
    assert "(no data)" in md
    # No energy or domains in frontmatter when empty
    assert "energy:" not in md
    assert "domains:" not in md


def test_multiple_domains_in_frontmatter() -> None:
    d = Distillation(
        date="2026-02-11",
        domain_tags=["engineer", "philosopher", "creative"],
        prompt_count=1,
        model="gemma3",
    )
    result = DistillationResult(distillation=d)
    md = format_distillation(result)
    assert "domains: [engineer, philosopher, creative]" in md


def test_delta_empty_sections() -> None:
    d = Distillation(date="2026-02-11", prompt_count=1, model="gemma3")
    delta = Delta(
        current_date="2026-02-11",
        previous_date="2026-02-10",
    )
    result = DistillationResult(distillation=d, delta=delta)
    md = format_distillation(result)

    assert "## Delta (from 2026-02-10)" in md
    assert "### New\n- (none)" in md
    assert "### Shifted\n- (none)" in md
    assert "### Faded\n- (none)" in md
    # No energy shift section when empty
    assert "### Energy Shift" not in md
