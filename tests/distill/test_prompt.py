"""Tests for prompt construction and response parsing."""

from __future__ import annotations

import json

from cc_trace.distill.models import DayPrompts
from cc_trace.distill.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    parse_distillation_response,
)


class TestBuildUserPrompt:
    def test_basic_format(self) -> None:
        day = DayPrompts(
            date="2026-02-11",
            prompts=["hello", "world"],
            prompt_count=2,
        )
        result = build_user_prompt(day)
        assert "2026-02-11" in result
        assert "プロンプト数: 2" in result
        assert "[1] hello" in result
        assert "[2] world" in result

    def test_gem_names_included(self) -> None:
        day = DayPrompts(
            date="2026-02-11",
            prompts=["test"],
            prompt_count=1,
            gem_names=["MyGem"],
        )
        result = build_user_prompt(day)
        assert "使用Gem: MyGem" in result

    def test_truncation_on_long_prompts(self) -> None:
        # Create prompts that exceed 6000 chars total
        long_prompt = "x" * 3500
        day = DayPrompts(
            date="2026-02-11",
            prompts=[long_prompt, long_prompt],
            prompt_count=2,
        )
        result = build_user_prompt(day)
        # Each prompt should be truncated to 200 chars
        lines = result.split("\n\n")
        # Find the prompt lines (skip header)
        prompt_lines = [l for l in lines if l.startswith("[")]
        for line in prompt_lines:
            # "[N] " prefix + 200 chars max
            content = line.split("] ", 1)[1]
            assert len(content) <= 200

    def test_no_truncation_under_threshold(self) -> None:
        day = DayPrompts(
            date="2026-02-11",
            prompts=["short prompt"] * 5,
            prompt_count=5,
        )
        result = build_user_prompt(day)
        assert "short prompt" in result

    def test_system_prompt_not_empty(self) -> None:
        assert len(SYSTEM_PROMPT) > 100
        assert "JSON" in SYSTEM_PROMPT


class TestParseDistillationResponse:
    def test_direct_json(self) -> None:
        raw = json.dumps({
            "core_topics": ["Python", "テスト"],
            "interests": ["プログラミング"],
            "mood_tension": "集中している",
            "energy_level": "high",
            "key_questions": ["効率的なテストとは?"],
            "domain_tags": ["engineer"],
        })
        result = parse_distillation_response(raw, "2026-02-11", "gemma3", 5)
        assert result.date == "2026-02-11"
        assert result.core_topics == ["Python", "テスト"]
        assert result.interests == ["プログラミング"]
        assert result.mood_tension == "集中している"
        assert result.energy_level == "high"
        assert result.key_questions == ["効率的なテストとは?"]
        assert result.domain_tags == ["engineer"]
        assert result.prompt_count == 5
        assert result.model == "gemma3"

    def test_fenced_json(self) -> None:
        raw = "Here is the analysis:\n```json\n" + json.dumps({
            "core_topics": ["topic1"],
            "interests": [],
            "mood_tension": "",
            "energy_level": "medium",
            "key_questions": [],
            "domain_tags": [],
        }) + "\n```"
        result = parse_distillation_response(raw, "2026-02-11", "gemma3", 1)
        assert result.core_topics == ["topic1"]
        assert result.energy_level == "medium"

    def test_brace_extraction(self) -> None:
        raw = 'Some text before {"core_topics": ["a"], "energy_level": "low"} and after'
        result = parse_distillation_response(raw, "2026-02-11", "gemma3", 1)
        assert result.core_topics == ["a"]
        assert result.energy_level == "low"

    def test_unparseable_fallback(self) -> None:
        raw = "This is not JSON at all."
        result = parse_distillation_response(raw, "2026-02-11", "gemma3", 3)
        assert result.date == "2026-02-11"
        assert result.core_topics == []
        assert result.prompt_count == 3
        assert result.model == "gemma3"

    def test_invalid_energy_level_normalized(self) -> None:
        raw = json.dumps({"energy_level": "SUPER HIGH"})
        result = parse_distillation_response(raw, "2026-02-11", "gemma3", 1)
        assert result.energy_level == ""

    def test_energy_level_case_insensitive(self) -> None:
        raw = json.dumps({"energy_level": "High"})
        result = parse_distillation_response(raw, "2026-02-11", "gemma3", 1)
        assert result.energy_level == "high"

    def test_scattered_energy(self) -> None:
        raw = json.dumps({"energy_level": "scattered"})
        result = parse_distillation_response(raw, "2026-02-11", "gemma3", 1)
        assert result.energy_level == "scattered"

    def test_missing_fields_default_empty(self) -> None:
        raw = json.dumps({"core_topics": ["only this"]})
        result = parse_distillation_response(raw, "2026-02-11", "gemma3", 1)
        assert result.core_topics == ["only this"]
        assert result.interests == []
        assert result.mood_tension == ""
