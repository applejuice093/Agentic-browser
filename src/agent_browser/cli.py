"""CLI entrypoint for agent-browser."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from agent_browser import Browser, __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-browser",
        description="AI Agent-First Browser CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    open_cmd = sub.add_parser("open", help="Open a URL and print a snapshot")
    open_cmd.add_argument("url", help="URL to open")
    open_cmd.add_argument("--headed", action="store_true", help="Run with UI (not headless)")
    open_cmd.add_argument(
        "--raw-html",
        action="store_true",
        help="Include raw HTML in snapshot (verbose)",
    )

    return parser


async def _cmd_open(url: str, *, headless: bool, include_raw_html: bool) -> int:
    async with Browser(headless=headless) as browser:
        page = await browser.open(url)
        snap = await page.snapshot(include_raw_html=include_raw_html)
        print(json.dumps(snap.model_dump(mode="json"), indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "open":
        code = asyncio.run(
            _cmd_open(
                args.url,
                headless=not args.headed,
                include_raw_html=args.raw_html,
            )
        )
        sys.exit(code)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
