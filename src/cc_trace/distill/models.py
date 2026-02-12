"""Data models for self-distillation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DayPrompts:
    """Aggregated prompts for a single day."""

    date: str  # YYYY-MM-DD
    prompts: list[str] = field(default_factory=list)
    prompt_count: int = 0
    gem_names: list[str] = field(default_factory=list)


@dataclass
class Distillation:
    """Extracted thinking patterns for a single day."""

    date: str
    core_topics: list[str] = field(default_factory=list)  # 3-7
    interests: list[str] = field(default_factory=list)  # 2-5
    mood_tension: str = ""  # free text
    energy_level: str = ""  # high/medium/low/scattered
    key_questions: list[str] = field(default_factory=list)  # 2-5
    domain_tags: list[str] = field(default_factory=list)
    prompt_count: int = 0
    model: str = ""


@dataclass
class Delta:
    """Difference between consecutive days' distillations."""

    current_date: str
    previous_date: str
    new_topics: list[str] = field(default_factory=list)
    shifted_topics: list[str] = field(default_factory=list)
    faded_topics: list[str] = field(default_factory=list)
    mood_shift: str = ""
    new_domains: list[str] = field(default_factory=list)
    lost_domains: list[str] = field(default_factory=list)


@dataclass
class DistillationResult:
    """Complete result for a day: distillation + optional delta."""

    distillation: Distillation
    delta: Delta | None = None
