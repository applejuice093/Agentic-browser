"""
M3 example: snapshot diffs + event stream + MutationObserver.

    python examples/events_diff.py
"""

from __future__ import annotations

import asyncio

from agent_browser import Browser, EventType

HTML = """
<!DOCTYPE html>
<html><head><title>Diff Demo</title></head>
<body>
  <button id="go" type="button">Add row</button>
  <ul id="list"></ul>
  <script>
    let i = 0;
    document.getElementById('go').onclick = () => {
      i++;
      const li = document.createElement('li');
      li.textContent = 'Row ' + i;
      document.getElementById('list').appendChild(li);
    };
  </script>
</body></html>
"""


async def main() -> None:
    async with Browser(headless=True) as browser:
        page = await browser.set_content(HTML)

        def log(e) -> None:
            et = e.event.value if hasattr(e.event, "value") else e.event
            if et in (
                EventType.PAGE_CHANGED.value,
                EventType.ELEMENT_ADDED.value,
                EventType.ELEMENT_CLICKED.value,
                EventType.MUTATION.value,
            ):
                print(f"  event: {et} {e.data}")

        page.on(log)

        await page.snapshot()
        print("baseline elements:", len(page.last_snapshot.elements or []))

        await page.click("#go")
        await page.snapshot()
        print("after click diff:", page.last_diff.summary() if page.last_diff else None)

        await page.watch(enabled=True, debounce_ms=40, auto_snapshot=True)
        await page.evaluate(
            """() => {
              const li = document.createElement('li');
              li.textContent = 'From mutation';
              document.getElementById('list').appendChild(li);
            }"""
        )
        try:
            await page.wait_for_event(EventType.MUTATION, timeout=3.0)
            print("mutation observed")
        except TimeoutError:
            print("mutation timeout (observer may still have fired async)")
        await asyncio.sleep(0.3)
        if page.last_diff:
            print("post-mutation diff:", page.last_diff.summary())
        await page.watch(enabled=False)


if __name__ == "__main__":
    asyncio.run(main())
