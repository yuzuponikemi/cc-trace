"""Configuration management for cc-trace."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


_DEFAULT_OBSIDIAN_INBOX = (
    "/Users/ikmx/Library/CloudStorage/"
    "GoogleDrive-yuzuponikemi@gmail.com/My Drive/ikmx-memo/08_cc-trace"
)

_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "cc-trace"


@dataclass
class GeminiConfig:
    """Configuration for Gemini module."""

    browser_state: Path = field(
        default_factory=lambda: _DEFAULT_CONFIG_DIR / "gemini-browser-state.json"
    )
    crawl_cache: Path = field(
        default_factory=lambda: _DEFAULT_CONFIG_DIR / "gemini-crawl-cache.json"
    )
    state_file: Path = field(
        default_factory=lambda: _DEFAULT_CONFIG_DIR / "gemini-sync-state.json"
    )


@dataclass
class Config:
    claude_dir: Path = field(default_factory=lambda: Path.home() / ".claude")
    obsidian_inbox: Path = field(
        default_factory=lambda: Path(_DEFAULT_OBSIDIAN_INBOX)
    )
    state_file: Path = field(
        default_factory=lambda: Path.home() / ".claude" / "cc-trace-state.json"
    )
    staleness_threshold: int = 300  # seconds since last modification
    verbose: bool = False
    gemini: GeminiConfig = field(default_factory=GeminiConfig)

    @property
    def projects_dir(self) -> Path:
        return self.claude_dir / "projects"

    @classmethod
    def load(cls, overrides: dict | None = None) -> Config:
        """Load config from TOML file, then apply CLI overrides."""
        config = cls()

        # Try loading from config file
        config_path = Path.home() / ".config" / "cc-trace" / "config.toml"
        if config_path.exists():
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            config = cls._apply_dict(config, data)

        # Apply CLI overrides
        if overrides:
            config = cls._apply_dict(config, overrides)

        return config

    @classmethod
    def _apply_dict(cls, config: Config, data: dict) -> Config:
        if "claude_dir" in data:
            config.claude_dir = Path(data["claude_dir"]).expanduser()
        if "obsidian_inbox" in data:
            config.obsidian_inbox = Path(data["obsidian_inbox"]).expanduser()
        if "state_file" in data:
            config.state_file = Path(data["state_file"]).expanduser()
        if "staleness_threshold" in data:
            config.staleness_threshold = int(data["staleness_threshold"])
        if "verbose" in data:
            config.verbose = bool(data["verbose"])

        # Apply Gemini config if present
        if "gemini" in data:
            gemini_data = data["gemini"]
            if "browser_state" in gemini_data:
                config.gemini.browser_state = Path(gemini_data["browser_state"]).expanduser()
            if "crawl_cache" in gemini_data:
                config.gemini.crawl_cache = Path(gemini_data["crawl_cache"]).expanduser()
            if "state_file" in gemini_data:
                config.gemini.state_file = Path(gemini_data["state_file"]).expanduser()

        return config
