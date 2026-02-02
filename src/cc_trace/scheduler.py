"""Cron job management for cc-trace."""

from __future__ import annotations

import shutil
import subprocess
import sys

_MARKER = "# cc-trace-auto"


def _get_uv_path() -> str:
    """Get the path to the uv binary."""
    uv = shutil.which("uv")
    if uv:
        return uv
    return "uv"


def _get_current_crontab() -> str:
    """Read the current crontab."""
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _write_crontab(content: str) -> None:
    """Write a new crontab via pipe."""
    subprocess.run(
        ["crontab", "-"],
        input=content,
        text=True,
        check=True,
    )


def _build_cron_entry() -> str:
    """Build the cron entry line."""
    uv = _get_uv_path()
    # Run cc-trace sync every hour at minute 0
    return f"0 * * * * {uv} run cc-trace sync >> ~/.claude/cc-trace.log 2>&1 {_MARKER}"


def install_cron() -> str:
    """Install the cc-trace cron job. Returns status message."""
    current = _get_current_crontab()
    entry = _build_cron_entry()

    # Check if already installed
    if _MARKER in current:
        # Replace existing entry
        lines = [
            line for line in current.splitlines()
            if _MARKER not in line
        ]
        lines.append(entry)
        _write_crontab("\n".join(lines) + "\n")
        return "Updated existing cc-trace cron job"

    # Add new entry
    new_content = current.rstrip("\n") + "\n" + entry + "\n" if current.strip() else entry + "\n"
    _write_crontab(new_content)
    return f"Installed cc-trace cron job: {entry}"


def uninstall_cron() -> str:
    """Remove the cc-trace cron job. Returns status message."""
    current = _get_current_crontab()

    if _MARKER not in current:
        return "No cc-trace cron job found"

    lines = [
        line for line in current.splitlines()
        if _MARKER not in line
    ]
    _write_crontab("\n".join(lines) + "\n" if lines else "")
    return "Removed cc-trace cron job"
