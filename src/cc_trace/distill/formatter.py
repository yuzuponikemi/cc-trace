"""Markdown formatter for distillation output."""

from __future__ import annotations

from cc_trace.distill.models import Delta, DistillationResult


def format_distillation(result: DistillationResult) -> str:
    """Format a DistillationResult as Obsidian Markdown.

    Returns:
        Complete Markdown string with frontmatter.
    """
    d = result.distillation
    lines: list[str] = []

    # Frontmatter
    lines.append("---")
    lines.append(f"created: {d.date}")
    lines.append("tags: [log/distill, type/self_observation]")
    lines.append("status: auto_generated")
    lines.append("source: gemini_distill")
    lines.append(f"prompt_count: {d.prompt_count}")
    lines.append(f"model: {d.model}")
    if d.energy_level:
        lines.append(f"energy: {d.energy_level}")
    if d.domain_tags:
        domains_str = ", ".join(d.domain_tags)
        lines.append(f"domains: [{domains_str}]")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# Self-Distillation: {d.date}")
    lines.append("")

    # Core Topics
    lines.append("## Core Topics")
    if d.core_topics:
        for topic in d.core_topics:
            lines.append(f"- {topic}")
    else:
        lines.append("- (none)")
    lines.append("")

    # Interests
    lines.append("## Interests")
    if d.interests:
        for interest in d.interests:
            lines.append(f"- {interest}")
    else:
        lines.append("- (none)")
    lines.append("")

    # Mood & Tension
    lines.append("## Mood & Tension")
    lines.append(d.mood_tension or "(no data)")
    lines.append("")

    # Key Questions
    lines.append("## Key Questions")
    if d.key_questions:
        for q in d.key_questions:
            lines.append(f"- {q}")
    else:
        lines.append("- (none)")
    lines.append("")

    # Domain Tags
    lines.append("## Domain Tags")
    if d.domain_tags:
        lines.append(", ".join(d.domain_tags))
    else:
        lines.append("(none)")
    lines.append("")

    # Delta
    if result.delta:
        _format_delta(lines, result.delta)

    return "\n".join(lines)


def _format_delta(lines: list[str], delta: Delta) -> None:
    """Append delta section to lines."""
    lines.append(f"## Delta (from {delta.previous_date})")

    lines.append("### New")
    if delta.new_topics:
        for t in delta.new_topics:
            lines.append(f"- {t}")
    else:
        lines.append("- (none)")

    lines.append("### Shifted")
    if delta.shifted_topics:
        for t in delta.shifted_topics:
            lines.append(f"- {t}")
    else:
        lines.append("- (none)")

    lines.append("### Faded")
    if delta.faded_topics:
        for t in delta.faded_topics:
            lines.append(f"- {t}")
    else:
        lines.append("- (none)")

    if delta.mood_shift:
        lines.append(f"### Energy Shift")
        lines.append(delta.mood_shift)

    if delta.new_domains:
        lines.append("### New Domains")
        lines.append(", ".join(delta.new_domains))

    if delta.lost_domains:
        lines.append("### Lost Domains")
        lines.append(", ".join(delta.lost_domains))

    lines.append("")
