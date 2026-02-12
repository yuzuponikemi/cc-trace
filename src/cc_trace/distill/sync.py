"""Pipeline orchestration for self-distillation."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from cc_trace.distill.aggregator import group_by_date
from cc_trace.distill.delta import compute_delta
from cc_trace.distill.formatter import format_distillation
from cc_trace.distill.models import Distillation, DistillationResult
from cc_trace.distill.ollama_client import OllamaClient, OllamaError
from cc_trace.distill.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    parse_distillation_response,
)
from cc_trace.gemini.takeout_parser import parse_takeout

if TYPE_CHECKING:
    from cc_trace.config import Config

logger = logging.getLogger(__name__)


def sync(
    config: Config,
    takeout_path: Path,
    inbox_override: Path | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int:
    """Run the distillation pipeline.

    Args:
        config: Application configuration.
        takeout_path: Path to My Activity.json.
        inbox_override: Optional override for output directory.
        date_from: Inclusive start date filter (YYYY-MM-DD).
        date_to: Inclusive end date filter (YYYY-MM-DD).

    Returns:
        Number of files written.
    """
    inbox = inbox_override or config.obsidian_inbox
    inbox.mkdir(parents=True, exist_ok=True)

    model = config.distill.ollama_model
    client = OllamaClient(
        base_url=config.distill.ollama_url,
        timeout=config.distill.ollama_timeout,
    )

    # Fail fast: check Ollama availability
    logger.info("Checking Ollama availability (model: %s)...", model)
    client.is_available(model)

    # Parse and aggregate
    entries = parse_takeout(takeout_path)
    if not entries:
        logger.warning("No entries found in Takeout file")
        return 0

    days = group_by_date(entries, date_from=date_from, date_to=date_to)
    if not days:
        logger.warning("No days in date range")
        return 0

    # Load state for dedup and delta
    state = _load_state(config.distill.state_file)

    written = 0
    for day in days:
        # Dedup gate: skip if prompt_count unchanged
        if _should_skip(day.date, day.prompt_count, state):
            logger.debug("Skipping %s: prompt_count unchanged", day.date)
            continue

        # Distill via Ollama
        logger.info("Distilling %s (%d prompts)...", day.date, day.prompt_count)
        try:
            distillation = _distill_day(client, model, day)
        except OllamaError as e:
            logger.error("Ollama error for %s: %s", day.date, e)
            continue

        # Compute delta from previous day's state
        delta = _compute_delta_from_state(distillation, state)

        result = DistillationResult(distillation=distillation, delta=delta)

        # Write Markdown
        content = format_distillation(result)
        filename = f"DIST-{day.date}.md"
        output_path = inbox / filename
        output_path.write_text(content, encoding="utf-8")
        logger.info("Wrote: %s", output_path)

        # Update state
        state[day.date] = {
            "prompt_count": day.prompt_count,
            "distillation": asdict(distillation),
        }
        written += 1

    _save_state(config.distill.state_file, state)
    logger.info("Distillation complete: %d file(s) written", written)
    return written


def _distill_day(client: OllamaClient, model: str, day) -> Distillation:
    """Call Ollama to distill a day's prompts."""
    user_prompt = build_user_prompt(day)
    raw = client.chat(model, SYSTEM_PROMPT, user_prompt)
    return parse_distillation_response(raw, day.date, model, day.prompt_count)


def _should_skip(date: str, prompt_count: int, state: dict) -> bool:
    """Check if distillation can be skipped (prompt_count unchanged)."""
    if date not in state:
        return False
    return state[date].get("prompt_count") == prompt_count


def _compute_delta_from_state(
    current: Distillation, state: dict
) -> None:
    """Look up previous day's distillation in state and compute delta."""
    # Find the most recent previous date in state
    prev_date = _find_previous_date(current.date, state)
    if prev_date is None:
        return None

    prev_data = state[prev_date].get("distillation")
    if prev_data is None:
        return None

    previous = Distillation(**prev_data)
    return compute_delta(current, previous)


def _find_previous_date(date: str, state: dict) -> str | None:
    """Find the most recent date before the given date in state."""
    dates = sorted(d for d in state if d < date)
    return dates[-1] if dates else None


def _load_state(state_file: Path) -> dict:
    """Load distill state from file."""
    if state_file.exists():
        try:
            with state_file.open(encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load distill state: %s", e)
    return {}


def _save_state(state_file: Path, state: dict) -> None:
    """Save distill state to file."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
