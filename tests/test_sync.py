"""Tests for the sync module."""

import json
import time
from pathlib import Path

from cc_trace.config import Config
from cc_trace.sync import _compute_hash, _load_state, _make_output_filename, sync
from cc_trace.parser import Session


def _create_test_env(tmp_path: Path) -> tuple[Path, Path, Path, Config]:
    """Create a test environment with projects dir, inbox, and state file."""
    projects_dir = tmp_path / "claude" / "projects" / "proj-myapp"
    projects_dir.mkdir(parents=True)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    state_file = tmp_path / "state.json"

    config = Config(
        claude_dir=tmp_path / "claude",
        obsidian_inbox=inbox,
        state_file=state_file,
        staleness_threshold=0,  # No staleness check in tests
    )
    return projects_dir, inbox, state_file, config


def _write_session_jsonl(projects_dir: Path, session_id: str = "test-sess") -> Path:
    """Write a minimal valid session JSONL."""
    path = projects_dir / f"{session_id}.jsonl"
    records = [
        {
            "type": "user",
            "userType": "external",
            "sessionId": session_id,
            "timestamp": "2026-02-02T10:00:00Z",
            "message": {"role": "user", "content": "Hello"},
        },
        {
            "type": "assistant",
            "message": {
                "model": "test-model",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "content": [{"type": "text", "text": "Hi there!"}],
            },
        },
    ]
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


def test_sync_processes_new_file(tmp_path):
    projects_dir, inbox, state_file, config = _create_test_env(tmp_path)
    _write_session_jsonl(projects_dir)

    count = sync(config)
    assert count == 1
    md_files = list(inbox.glob("*.md"))
    assert len(md_files) == 1
    assert md_files[0].name.startswith("CC-")
    content = md_files[0].read_text()
    assert "Hello" in content
    assert "Hi there!" in content


def test_sync_skips_duplicate(tmp_path):
    projects_dir, inbox, state_file, config = _create_test_env(tmp_path)
    _write_session_jsonl(projects_dir)

    # First run
    count1 = sync(config)
    assert count1 == 1

    # Second run - same file, should skip
    count2 = sync(config)
    assert count2 == 0


def test_sync_reprocesses_changed_file(tmp_path):
    projects_dir, inbox, state_file, config = _create_test_env(tmp_path)
    path = _write_session_jsonl(projects_dir)

    # First run
    sync(config)

    # Modify file
    with open(path, "a") as f:
        record = {
            "type": "user",
            "userType": "external",
            "sessionId": "test-sess",
            "timestamp": "2026-02-02T11:00:00Z",
            "message": {"role": "user", "content": "New question"},
        }
        f.write(json.dumps(record) + "\n")

    # Second run - file changed, should reprocess
    count = sync(config)
    assert count == 1


def test_sync_staleness_threshold(tmp_path):
    projects_dir, inbox, state_file, config = _create_test_env(tmp_path)
    config.staleness_threshold = 9999  # Very high threshold
    _write_session_jsonl(projects_dir)

    # File was just created, so mtime is recent -> should be skipped
    count = sync(config)
    assert count == 0


def test_sync_no_projects_dir(tmp_path):
    config = Config(
        claude_dir=tmp_path / "nonexistent",
        obsidian_inbox=tmp_path / "inbox",
        state_file=tmp_path / "state.json",
    )
    count = sync(config)
    assert count == 0


def test_make_output_filename():
    session = Session(
        session_id="abc12345-dead-beef",
        project="myapp",
        started_at="2026-02-02T10:00:00Z",
    )
    name = _make_output_filename(session)
    assert name == "CC-2026-02-02-myapp-abc12345.md"


def test_load_state_missing_file(tmp_path):
    state = _load_state(tmp_path / "nonexistent.json")
    assert state == {}


def test_compute_hash(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    h1 = _compute_hash(f)
    assert len(h1) == 64  # SHA-256 hex digest

    f.write_text("world")
    h2 = _compute_hash(f)
    assert h1 != h2
