"""Sync session logs to Obsidian inbox with deduplication."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

from .config import Config
from .parser import parse_session
from .transformer import transform_session

logger = logging.getLogger(__name__)


def _compute_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_state(state_file: Path) -> dict:
    """Load the state file tracking processed sessions."""
    if state_file.exists():
        try:
            with open(state_file, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt state file, starting fresh")
    return {}


def _save_state(state_file: Path, state: dict) -> None:
    """Save the state file."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _make_output_filename(session) -> str:
    """Generate output filename: CC-{date}-{project}-{session_short}.md"""
    date_str = "unknown"
    if session.started_at:
        try:
            date_str = session.started_at[:10]
        except (IndexError, TypeError):
            pass

    project = session.project or "unknown"
    session_short = session.session_id[:8] if session.session_id else "unknown"

    return f"CC-{date_str}-{project}-{session_short}.md"


def sync(config: Config) -> int:
    """Sync all eligible session logs to Obsidian inbox.

    Returns the number of files processed.
    """
    projects_dir = config.projects_dir
    if not projects_dir.exists():
        logger.info("Projects directory does not exist: %s", projects_dir)
        return 0

    state = _load_state(config.state_file)
    processed_count = 0
    now = time.time()

    # Find all JSONL files
    jsonl_files = sorted(projects_dir.rglob("*.jsonl"))
    logger.info("Found %d JSONL files", len(jsonl_files))

    for jsonl_path in jsonl_files:
        path_key = str(jsonl_path)

        # Check staleness: skip files still being actively written
        mtime = jsonl_path.stat().st_mtime
        if (now - mtime) < config.staleness_threshold:
            logger.debug("Skipping (still active): %s", jsonl_path.name)
            continue

        # Check hash for deduplication
        file_hash = _compute_hash(jsonl_path)
        if state.get(path_key) == file_hash:
            logger.debug("Skipping (unchanged): %s", jsonl_path.name)
            continue

        # Parse and transform
        try:
            session = parse_session(jsonl_path)
        except Exception:
            logger.exception("Failed to parse: %s", jsonl_path.name)
            continue

        if not session.messages:
            logger.debug("Skipping (no messages): %s", jsonl_path.name)
            state[path_key] = file_hash
            _save_state(config.state_file, state)
            continue

        markdown = transform_session(session)
        filename = _make_output_filename(session)

        # Write to Obsidian inbox
        output_path = config.obsidian_inbox / filename
        config.obsidian_inbox.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        logger.info("Wrote: %s", output_path)

        # Update state
        state[path_key] = file_hash
        _save_state(config.state_file, state)
        processed_count += 1

    return processed_count
