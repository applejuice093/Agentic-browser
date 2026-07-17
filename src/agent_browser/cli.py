"""CLI entrypoint for agent-browser (M1)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Sequence

from agent_browser import Browser, __version__
from agent_browser.exceptions import AgentBrowserError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-browser",
        description="AI Agent-First Browser CLI (M1: open + snapshot)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run with browser UI (not headless)",
    )
    parser.add_argument(
        "--browser",
        choices=("chromium", "firefox", "webkit"),
        default="chromium",
        help="Underlying browser engine (default: chromium)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30_000,
        metavar="MS",
        help="Default timeout in milliseconds (default: 30000)",
    )

    sub = parser.add_subparsers(dest="command")

    open_cmd = sub.add_parser("open", help="Open a URL and print a JSON snapshot")
    open_cmd.add_argument("url", help="URL to open (http(s):// or file://)")
    open_cmd.add_argument(
        "--raw-html",
        action="store_true",
        help="Include raw HTML in the snapshot",
    )
    open_cmd.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON (no indentation)",
    )

    version_cmd = sub.add_parser("version", help="Print package version")
    version_cmd.set_defaults(command="version")

    scrape_cmd = sub.add_parser(
        "scrape",
        help="Scrape a URL into structured JSON (agent semantic model)",
    )
    scrape_cmd.add_argument("url", help="URL to scrape")
    scrape_cmd.add_argument(
        "-o",
        "--out",
        default="-",
        help="Output file path, or - for stdout (default)",
    )
    scrape_cmd.add_argument(
        "--goal",
        default="extract main content and key links",
        help="Goal string passed into page.context()",
    )

    return parser


async def _cmd_open(
    url: str,
    *,
    headless: bool,
    browser_type: str,
    timeout_ms: int,
    include_raw_html: bool,
    compact: bool,
) -> int:
    async with Browser(
        headless=headless,
        browser_type=browser_type,  # type: ignore[arg-type]
        default_timeout_ms=timeout_ms,
    ) as browser:
        page = await browser.open(url)
        snap = await page.snapshot(include_raw_html=include_raw_html)
        payload = snap.model_dump(mode="json")
        if compact:
            print(json.dumps(payload, default=str, separators=(",", ":")))
        else:
            print(json.dumps(payload, indent=2, default=str))
    return 0


async def _cmd_scrape(
    url: str,
    *,
    headless: bool,
    browser_type: str,
    timeout_ms: int,
    out: str,
    goal: str,
) -> int:
    from agent_browser.scrape import scrape_page

    async with Browser(
        headless=headless,
        browser_type=browser_type,  # type: ignore[arg-type]
        default_timeout_ms=timeout_ms,
    ) as browser:
        page = await browser.open(url)
        payload = await scrape_page(page, include_network=True, goal=goal)
        payload["session_id"] = browser.session_id
        text = json.dumps(payload, indent=2, default=str)
        if out == "-" or out == "":
            print(text)
        else:
            from pathlib import Path

            path = Path(out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path} ({payload.get('counts')})", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command is None:
        parser.print_help()
        raise SystemExit(0)

    if args.command == "version":
        print(__version__)
        raise SystemExit(0)

    if args.command == "open":
        try:
            code = asyncio.run(
                _cmd_open(
                    args.url,
                    headless=not args.headed,
                    browser_type=args.browser,
                    timeout_ms=args.timeout,
                    include_raw_html=args.raw_html,
                    compact=args.compact,
                )
            )
        except AgentBrowserError as exc:
            print(f"error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        raise SystemExit(code)

    if args.command == "scrape":
        try:
            code = asyncio.run(
                _cmd_scrape(
                    args.url,
                    headless=not args.headed,
                    browser_type=args.browser,
                    timeout_ms=args.timeout,
                    out=args.out,
                    goal=args.goal,
                )
            )
        except AgentBrowserError as exc:
            print(f"error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        raise SystemExit(code)

    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
