"""CLI entry point for cc-trace."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

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


def _handle_gemini_login(args: argparse.Namespace, config: Config) -> int:
    """Handle gemini login command."""
    from .gemini.crawler import login

    timeout = getattr(args, "timeout", 120)
    success = login(config, timeout=timeout)
    if success:
        print("Login successful. Browser state saved.")
        return 0
    else:
        print("Login failed or timed out.")
        return 1


def _handle_gemini_crawl(args: argparse.Namespace, config: Config) -> int:
    """Handle gemini crawl command."""
    from .gemini.crawler import crawl

    timeout = getattr(args, "timeout", 30)
    limit = getattr(args, "limit", 0)
    count = crawl(config, timeout=timeout, limit=limit)
    print(f"Crawled {count} conversation(s)")
    return 0


def _handle_gemini_sync(args: argparse.Namespace, config: Config) -> int:
    """Handle gemini sync command."""
    from .gemini.sync import sync as gemini_sync

    takeout_path = Path(args.takeout).expanduser()
    if not takeout_path.exists():
        print(f"Takeout file not found: {takeout_path}")
        return 1

    inbox_override = None
    if args.inbox:
        inbox_override = Path(args.inbox).expanduser()

    count = gemini_sync(config, takeout_path, inbox_override=inbox_override)
    print(f"Wrote {count} file(s)")
    return 0


def _handle_distill(args: argparse.Namespace, config: Config) -> int:
    """Handle distill command."""
    from .distill.ollama_client import OllamaError
    from .distill.sync import sync as distill_sync

    takeout_path = Path(args.takeout).expanduser()
    if not takeout_path.exists():
        print(f"Takeout file not found: {takeout_path}")
        return 1

    inbox_override = None
    if args.inbox:
        inbox_override = Path(args.inbox).expanduser()

    # Apply CLI overrides to distill config
    if args.model:
        config.distill.ollama_model = args.model
    if args.ollama_url:
        config.distill.ollama_url = args.ollama_url

    date_from = getattr(args, "from", None)
    date_to = args.to

    try:
        count = distill_sync(
            config,
            takeout_path,
            inbox_override=inbox_override,
            date_from=date_from,
            date_to=date_to,
        )
        print(f"Distilled {count} day(s)")
        return 0
    except OllamaError as e:
        print(f"Ollama error: {e}")
        return 1


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

    # distill subcommand
    distill_parser = subparsers.add_parser(
        "distill", help="Distill daily thinking patterns from Gemini conversations"
    )
    distill_parser.add_argument(
        "--takeout", type=str, required=True,
        help="Path to My Activity.json from Google Takeout"
    )
    distill_parser.add_argument("--inbox", type=str, help="Override Obsidian inbox path")
    distill_parser.add_argument(
        "--from", type=str, default=None, dest="from",
        help="Start date filter (YYYY-MM-DD, inclusive)"
    )
    distill_parser.add_argument(
        "--to", type=str, default=None,
        help="End date filter (YYYY-MM-DD, inclusive)"
    )
    distill_parser.add_argument(
        "--model", type=str, default=None,
        help="Ollama model name (default: gemma3)"
    )
    distill_parser.add_argument(
        "--ollama-url", type=str, default=None, dest="ollama_url",
        help="Ollama API URL (default: http://localhost:11434)"
    )
    distill_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    # gemini subcommand group
    gemini_parser = subparsers.add_parser("gemini", help="Gemini conversation tools")
    gemini_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    gemini_subparsers = gemini_parser.add_subparsers(dest="gemini_command")

    # gemini login
    gemini_login_parser = gemini_subparsers.add_parser(
        "login", help="Login to Gemini in browser"
    )
    gemini_login_parser.add_argument(
        "--timeout", type=int, default=120,
        help="Login timeout in seconds (default: 120)"
    )

    # gemini crawl
    gemini_crawl_parser = gemini_subparsers.add_parser(
        "crawl", help="Crawl Gemini conversation structure"
    )
    gemini_crawl_parser.add_argument(
        "--timeout", type=int, default=30,
        help="Page load timeout in seconds (default: 30)"
    )
    gemini_crawl_parser.add_argument(
        "--limit", type=int, default=0,
        help="Max conversations to crawl (0 = all)"
    )

    # gemini sync
    gemini_sync_parser = gemini_subparsers.add_parser(
        "sync", help="Sync Takeout + crawl data to Obsidian"
    )
    gemini_sync_parser.add_argument(
        "--takeout", type=str, required=True,
        help="Path to My Activity.json from Google Takeout"
    )
    gemini_sync_parser.add_argument(
        "--inbox", type=str,
        help="Override Obsidian inbox path"
    )

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

    if args.command == "distill":
        overrides = {}
        if args.inbox:
            overrides["obsidian_inbox"] = args.inbox
        if args.verbose:
            overrides["verbose"] = True
        config = Config.load(overrides)
        return _handle_distill(args, config)

    if args.command == "gemini":
        if not args.gemini_command:
            gemini_parser.print_help()
            return 1

        config = Config.load()

        if args.gemini_command == "login":
            return _handle_gemini_login(args, config)
        elif args.gemini_command == "crawl":
            return _handle_gemini_crawl(args, config)
        elif args.gemini_command == "sync":
            return _handle_gemini_sync(args, config)

    return 1


if __name__ == "__main__":
    sys.exit(main())
