"""
M2 example: semantic snapshot, stable IDs, and find().

    python examples/semantic_find.py
"""

from __future__ import annotations

import asyncio
import json

from agent_browser import Browser

HTML = """
<!DOCTYPE html>
<html>
<head><title>Cart</title></head>
<body>
  <main>
    <h1>Your Cart</h1>
    <div class="noise"><div></div></div>
    <ul>
      <li>Widget × 1</li>
    </ul>
    <button id="checkout" type="button">Checkout</button>
    <p id="msg">ready</p>
  </main>
  <script>
    document.getElementById('checkout').onclick = () => {
      document.getElementById('msg').textContent = 'checking out';
    };
  </script>
</body>
</html>
"""


async def main() -> None:
    async with Browser(headless=True) as browser:
        page = await browser.set_content(HTML)

        snap1 = await page.snapshot()
        print("elements:", len(snap1.elements))
        print(
            json.dumps(
                [
                    {
                        "id": e.id,
                        "role": e.role,
                        "type": e.type,
                        "text": e.text,
                        "parent_id": e.parent_id,
                        "children_ids": e.children_ids,
                    }
                    for e in snap1.elements
                ],
                indent=2,
            )
        )

        btn = await page.find(role="button", text_contains="Checkout")
        assert btn is not None
        print("found checkout id=", btn.id)
        await page.click(btn.id)

        snap2 = await page.snapshot()
        btn2 = next(e for e in snap2.elements if e.attributes.get("id") == "checkout")
        print("stable id unchanged:", btn.id == btn2.id)
        msg = await page.evaluate("() => document.getElementById('msg').textContent")
        print("msg:", msg)


if __name__ == "__main__":
    asyncio.run(main())
