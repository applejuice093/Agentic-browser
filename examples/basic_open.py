"""
M1 example: open a page and print a semantic-ish snapshot.

Usage (from repo root, with package installed and Chromium available):

    pip install -e ".[dev]"
    playwright install chromium
    python examples/basic_open.py
"""

from __future__ import annotations

import asyncio
import json

from agent_browser import Browser


async def main() -> None:
    async with Browser(headless=True) as browser:
        page = await browser.open("https://example.com")
        snap = await page.snapshot()
        print(json.dumps(snap.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
