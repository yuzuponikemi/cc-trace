"""Configuration management for cc-trace."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


_DEFAULT_OBSIDIAN_INBOX = (
    "/Users/ikmx/Library/CloudStorage/"
    "GoogleDrive-yuzuponikemi@gmail.com/My Drive/ikmx-memo"
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
        return config
