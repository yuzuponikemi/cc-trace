"""CLI entry point for cc-trace."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import Config
from .scheduler import install_cron, uninstall_cron
from .sync import sync


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
        stream=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cc-trace",
        description="Extract Claude Code session logs into Obsidian Markdown",
    )
    subparsers = parser.add_subparsers(dest="command")

    # sync subcommand
    sync_parser = subparsers.add_parser("sync", help="Sync session logs to Obsidian")
    sync_parser.add_argument("--inbox", type=str, help="Override Obsidian inbox path")
    sync_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    # cron subcommand
    cron_parser = subparsers.add_parser("cron", help="Manage cron job")
    cron_group = cron_parser.add_mutually_exclusive_group(required=True)
    cron_group.add_argument("--install", action="store_true", help="Install cron job")
    cron_group.add_argument("--uninstall", action="store_true", help="Uninstall cron job")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    _setup_logging(getattr(args, "verbose", False))

    if args.command == "sync":
        overrides = {}
        if args.inbox:
            overrides["obsidian_inbox"] = args.inbox
        if args.verbose:
            overrides["verbose"] = True

        config = Config.load(overrides)
        count = sync(config)
        print(f"Processed {count} session(s)")
        return 0

    if args.command == "cron":
        if args.install:
            msg = install_cron()
        else:
            msg = uninstall_cron()
        print(msg)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
