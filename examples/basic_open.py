"""
M1 example: open a page (offline HTML) and interact via snapshot IDs.

Usage:

    pip install -e ".[dev]"
    playwright install chromium
    python examples/basic_open.py
"""

from __future__ import annotations

import asyncio
import json

from agent_browser import Browser

HTML = """
<!DOCTYPE html>
<html>
  <head><title>Demo Shop</title></head>
  <body>
    <h1>Demo Shop</h1>
    <input id="q" name="q" placeholder="Search" />
    <button id="go" type="button">Search</button>
    <p id="out">ready</p>
    <script>
      document.getElementById('go').onclick = () => {
        document.getElementById('out').textContent =
          'query=' + document.getElementById('q').value;
      };
    </script>
  </body>
</html>
"""


async def main() -> None:
    async with Browser(headless=True) as browser:
        page = await browser.set_content(HTML)
        snap = await page.snapshot()
        print("title:", snap.title)
        print("elements:", json.dumps([e.model_dump() for e in snap.elements], indent=2))

        search = next(e for e in snap.elements if e.attributes.get("id") == "q")
        go = next(
            e
            for e in snap.elements
            if e.type == "button" and e.attributes.get("id") == "go"
        )

        await page.fill(search.id, "wireless headphones")
        await page.click(go.id)

        out = await page.evaluate("() => document.getElementById('out').textContent")
        print("result:", out)


if __name__ == "__main__":
    asyncio.run(main())
