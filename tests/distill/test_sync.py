"""Tests for distill sync orchestration."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

from cc_trace.distill.sync import (
    _compute_delta_from_state,
    _find_previous_date,
    _load_state,
    _save_state,
    _should_skip,
    sync,
)
from cc_trace.distill.models import Distillation


@dataclass
class MockDistillConfig:
    state_file: Path = field(default_factory=lambda: Path("/tmp/distill-state.json"))
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3"
    ollama_timeout: int = 120


@dataclass
class MockConfig:
    obsidian_inbox: Path = field(default_factory=lambda: Path("/tmp/inbox"))
    distill: MockDistillConfig = field(default_factory=MockDistillConfig)


def _write_takeout(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(entries, f)


def _make_takeout_entry(prompt: str, timestamp: str) -> dict:
    return {
        "title": f"Prompted {prompt}",
        "time": timestamp,
        "safeHtmlItem": [{"html": f"<p>response to {prompt}</p>"}],
    }


class TestShouldSkip:
    def test_new_date(self) -> None:
        assert _should_skip("2026-02-11", 5, {}) is False

    def test_same_count(self) -> None:
        state = {"2026-02-11": {"prompt_count": 5}}
        assert _should_skip("2026-02-11", 5, state) is True

    def test_different_count(self) -> None:
        state = {"2026-02-11": {"prompt_count": 3}}
        assert _should_skip("2026-02-11", 5, state) is False


class TestFindPreviousDate:
    def test_no_state(self) -> None:
        assert _find_previous_date("2026-02-11", {}) is None

    def test_previous_exists(self) -> None:
        state = {"2026-02-09": {}, "2026-02-10": {}}
        assert _find_previous_date("2026-02-11", state) == "2026-02-10"

    def test_no_previous(self) -> None:
        state = {"2026-02-12": {}}
        assert _find_previous_date("2026-02-11", state) is None

    def test_gap_in_dates(self) -> None:
        state = {"2026-02-05": {}, "2026-02-08": {}}
        assert _find_previous_date("2026-02-11", state) == "2026-02-08"


class TestComputeDeltaFromState:
    def test_no_previous(self) -> None:
        current = Distillation(date="2026-02-11")
        result = _compute_delta_from_state(current, {})
        assert result is None

    def test_with_previous(self) -> None:
        current = Distillation(
            date="2026-02-11",
            core_topics=["A", "B"],
            energy_level="high",
        )
        state = {
            "2026-02-10": {
                "distillation": {
                    "date": "2026-02-10",
                    "core_topics": ["A", "C"],
                    "interests": [],
                    "mood_tension": "",
                    "energy_level": "low",
                    "key_questions": [],
                    "domain_tags": [],
                    "prompt_count": 3,
                    "model": "gemma3",
                }
            }
        }
        delta = _compute_delta_from_state(current, state)
        assert delta is not None
        assert delta.current_date == "2026-02-11"
        assert delta.previous_date == "2026-02-10"
        assert "B" in delta.new_topics
        assert "C" in delta.faded_topics


class TestStateIO:
    def test_load_nonexistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "nonexistent.json"
            assert _load_state(state_file) == {}

    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state = {"2026-02-11": {"prompt_count": 5}}
            _save_state(state_file, state)
            loaded = _load_state(state_file)
            assert loaded == state

    def test_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "nested" / "dir" / "state.json"
            _save_state(state_file, {"key": "val"})
            assert state_file.exists()


class TestSync:
    def test_empty_takeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            takeout = tmppath / "activity.json"
            inbox = tmppath / "inbox"
            state_file = tmppath / "state.json"

            _write_takeout(takeout, [])

            config = MockConfig(
                obsidian_inbox=inbox,
                distill=MockDistillConfig(state_file=state_file),
            )

            with patch("cc_trace.distill.sync.OllamaClient") as MockClient:
                MockClient.return_value.is_available.return_value = True
                result = sync(config, takeout)

            assert result == 0

    def test_single_day_distillation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            takeout = tmppath / "activity.json"
            inbox = tmppath / "inbox"
            state_file = tmppath / "state.json"

            _write_takeout(takeout, [
                _make_takeout_entry("hello", "2026-02-11T10:00:00.000Z"),
                _make_takeout_entry("world", "2026-02-11T14:00:00.000Z"),
            ])

            config = MockConfig(
                obsidian_inbox=inbox,
                distill=MockDistillConfig(state_file=state_file),
            )

            ollama_response = json.dumps({
                "core_topics": ["greeting"],
                "interests": ["communication"],
                "mood_tension": "friendly",
                "energy_level": "medium",
                "key_questions": ["how to greet?"],
                "domain_tags": ["life"],
            })

            with patch("cc_trace.distill.sync.OllamaClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.is_available.return_value = True
                mock_instance.chat.return_value = ollama_response

                result = sync(config, takeout)

            assert result == 1

            files = list(inbox.glob("*.md"))
            assert len(files) == 1
            assert files[0].name == "DIST-2026-02-11.md"

            content = files[0].read_text()
            assert "greeting" in content
            assert "Self-Distillation: 2026-02-11" in content
            assert "prompt_count: 2" in content

    def test_dedup_skips_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            takeout = tmppath / "activity.json"
            inbox = tmppath / "inbox"
            state_file = tmppath / "state.json"

            _write_takeout(takeout, [
                _make_takeout_entry("hello", "2026-02-11T10:00:00.000Z"),
            ])

            # Pre-seed state with same prompt_count
            state = {"2026-02-11": {"prompt_count": 1}}
            with state_file.open("w") as f:
                json.dump(state, f)

            config = MockConfig(
                obsidian_inbox=inbox,
                distill=MockDistillConfig(state_file=state_file),
            )

            with patch("cc_trace.distill.sync.OllamaClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.is_available.return_value = True

                result = sync(config, takeout)

            assert result == 0
            # chat should never be called
            mock_instance.chat.assert_not_called()

    def test_date_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            takeout = tmppath / "activity.json"
            inbox = tmppath / "inbox"
            state_file = tmppath / "state.json"

            _write_takeout(takeout, [
                _make_takeout_entry("old", "2026-02-09T10:00:00.000Z"),
                _make_takeout_entry("target", "2026-02-11T10:00:00.000Z"),
                _make_takeout_entry("future", "2026-02-13T10:00:00.000Z"),
            ])

            config = MockConfig(
                obsidian_inbox=inbox,
                distill=MockDistillConfig(state_file=state_file),
            )

            ollama_response = json.dumps({
                "core_topics": ["target"],
                "energy_level": "high",
            })

            with patch("cc_trace.distill.sync.OllamaClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.is_available.return_value = True
                mock_instance.chat.return_value = ollama_response

                result = sync(
                    config, takeout,
                    date_from="2026-02-10", date_to="2026-02-12",
                )

            assert result == 1
            files = list(inbox.glob("*.md"))
            assert len(files) == 1
            assert files[0].name == "DIST-2026-02-11.md"

    def test_ollama_error_continues(self) -> None:
        """Ollama errors for one day don't stop processing others."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            takeout = tmppath / "activity.json"
            inbox = tmppath / "inbox"
            state_file = tmppath / "state.json"

            _write_takeout(takeout, [
                _make_takeout_entry("day1", "2026-02-10T10:00:00.000Z"),
                _make_takeout_entry("day2", "2026-02-11T10:00:00.000Z"),
            ])

            config = MockConfig(
                obsidian_inbox=inbox,
                distill=MockDistillConfig(state_file=state_file),
            )

            from cc_trace.distill.ollama_client import OllamaError

            ollama_response = json.dumps({"core_topics": ["ok"]})

            with patch("cc_trace.distill.sync.OllamaClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.is_available.return_value = True
                # First call fails, second succeeds
                mock_instance.chat.side_effect = [
                    OllamaError("timeout"),
                    ollama_response,
                ]

                result = sync(config, takeout)

            assert result == 1  # Only second day succeeded

    def test_inbox_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            takeout = tmppath / "activity.json"
            default_inbox = tmppath / "default"
            custom_inbox = tmppath / "custom"
            state_file = tmppath / "state.json"

            _write_takeout(takeout, [
                _make_takeout_entry("test", "2026-02-11T10:00:00.000Z"),
            ])

            config = MockConfig(
                obsidian_inbox=default_inbox,
                distill=MockDistillConfig(state_file=state_file),
            )

            ollama_response = json.dumps({"core_topics": ["test"]})

            with patch("cc_trace.distill.sync.OllamaClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.is_available.return_value = True
                mock_instance.chat.return_value = ollama_response

                result = sync(config, takeout, inbox_override=custom_inbox)

            assert result == 1
            assert len(list(custom_inbox.glob("*.md"))) == 1
            assert not default_inbox.exists() or len(list(default_inbox.glob("*.md"))) == 0
