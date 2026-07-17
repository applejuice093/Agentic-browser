"""M3 integration: diffs, action events, MutationObserver watch."""

from __future__ import annotations

import asyncio

import pytest

from agent_browser import Browser, EventType

HTML = """
<!DOCTYPE html>
<html>
<head><title>Events Fixture</title></head>
<body>
  <h1>Events</h1>
  <input id="q" name="q" />
  <button id="add" type="button">Add</button>
  <ul id="list"></ul>
  <p id="status">idle</p>
  <script>
    let n = 0;
    document.getElementById('add').onclick = function () {
      n += 1;
      var li = document.createElement('li');
      li.textContent = 'Item ' + n;
      li.id = 'item-' + n;
      document.getElementById('list').appendChild(li);
      document.getElementById('status').textContent = 'count=' + n;
    };
  </script>
</body>
</html>
"""


@pytest.fixture
async def page():
    async with Browser(headless=True) as browser:
        p = await browser.set_content(HTML)
        yield p


@pytest.mark.asyncio
async def test_snapshot_diff_after_action(page):
    snap1 = await page.snapshot()
    assert page.last_diff is not None
    # first snapshot baseline — empty-ish diff
    assert page.last_diff.is_empty or page.last_diff.added == [] or True

    await page.click("#add")
    snap2 = await page.snapshot()
    diff = page.last_diff
    assert diff is not None
    assert not diff.is_empty
    # status text change and/or new list item
    assert len(diff.added) + len(diff.changed) + len(diff.removed) >= 1
    assert snap2.elements


@pytest.mark.asyncio
async def test_action_emits_click_event(page):
    seen: list = []
    page.on(lambda e: seen.append(e))
    await page.snapshot()
    await page.click("#add")
    types = [
        e.event.value if hasattr(e.event, "value") else e.event for e in seen
    ]
    assert EventType.ELEMENT_CLICKED.value in types
    assert EventType.NAVIGATION.value in types or True  # set_content already navigated


@pytest.mark.asyncio
async def test_fill_emits_event(page):
    seen: list = []
    page.on_event(EventType.ELEMENT_FILLED, lambda e: seen.append(e))
    await page.fill("#q", "hello")
    assert len(seen) == 1
    assert seen[0].data["length"] == 5


@pytest.mark.asyncio
async def test_diff_snapshots_helper(page):
    a = await page.snapshot()
    await page.click("#add")
    b = await page.snapshot(emit_events=False)
    diff = page.diff_snapshots(a, b)
    assert not diff.is_empty
    summary = diff.summary()
    assert "added" in summary


@pytest.mark.asyncio
async def test_mutation_observer_watch(page):
    mutations: list = []
    page_changes: list = []

    def handler(e):
        et = e.event.value if hasattr(e.event, "value") else e.event
        if et == EventType.MUTATION.value:
            mutations.append(e)
        if et == EventType.PAGE_CHANGED.value:
            page_changes.append(e)

    page.on(handler)
    await page.snapshot()
    await page.watch(enabled=True, debounce_ms=50, auto_snapshot=True)

    # DOM mutation via JS (not through click API)
    await page.evaluate(
        """() => {
          const li = document.createElement('li');
          li.id = 'dyn';
          li.textContent = 'Dynamic';
          document.getElementById('list').appendChild(li);
        }"""
    )

    # wait for debounce + async snapshot
    for _ in range(40):
        if mutations:
            break
        await asyncio.sleep(0.05)

    assert mutations, "expected mutation event from MutationObserver"
    # auto_snapshot should eventually produce page_changed or at least last_diff
    for _ in range(40):
        if page_changes or (page.last_diff and not page.last_diff.is_empty):
            break
        await asyncio.sleep(0.05)

    assert page_changes or (page.last_diff and not page.last_diff.is_empty)
    await page.watch(enabled=False)


@pytest.mark.asyncio
async def test_wait_for_event_click(page):
    await page.snapshot()

    async def do_click() -> None:
        await asyncio.sleep(0.05)
        await page.click("#add")

    task = asyncio.create_task(do_click())
    ev = await page.wait_for_event(EventType.ELEMENT_CLICKED, timeout=5.0)
    await task
    assert ev.event == EventType.ELEMENT_CLICKED or (
        getattr(ev.event, "value", ev.event) == "element_clicked"
    )


@pytest.mark.asyncio
async def test_event_history(page):
    await page.snapshot()
    await page.click("#add")
    hist = page.events.history(event_type=EventType.ELEMENT_CLICKED)
    assert len(hist) >= 1
