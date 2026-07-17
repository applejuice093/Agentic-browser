# M3 — Incremental Diffs & Event Streaming

**Branch:** `milestone/m3-diffs-events`  
**Goal:** DOM/semantic diffs, event bus, MutationObserver live updates.

## Acceptance

| Item | Status |
|------|--------|
| `Diff` between snapshots | Done |
| Event bus: navigation, element_added/removed, etc. | Done |
| Optional MutationObserver path | Done (`page.watch()`) |

## Diff model

```json
{
  "added": [{ "id": 87, "role": "button", "text": "Login", "...": "..." }],
  "removed": [42, 45],
  "changed": [{ "id": 10, "text": "2 items", "previous_text": "1 item" }],
  "url_changed": false,
  "title_changed": false
}
```

`page.snapshot()` always updates `page.last_diff` when a prior snapshot exists.

## Events

| Event | When |
|-------|------|
| `navigation` | `goto` / `set_content` / reload / back / forward |
| `snapshot` | First snapshot baseline |
| `element_added` / `element_removed` | From diff expansion |
| `text_changed` / `value_changed` | Field-level diff |
| `page_changed` | Aggregate diff summary |
| `element_clicked` / `element_typed` / `element_filled` | Actions |
| `mutation` | MutationObserver batch |
| `error` | Watch/snapshot failures |

## API

```python
async with Browser() as browser:
    page = await browser.set_content(html)

    page.on(lambda e: print(e.event, e.data))
    snap1 = await page.snapshot()

    await page.click("#add")
    snap2 = await page.snapshot()
    print(page.last_diff.summary())

    # Live watch
    await page.watch(enabled=True, debounce_ms=100, auto_snapshot=True)
    # ... page mutates ...
    await page.wait_for_event("page_changed", timeout=5)
    await page.watch(enabled=False)
```

### Helpers

| Method | Purpose |
|--------|---------|
| `page.diff_snapshots(a, b)` | Pure diff, no side effects |
| `page.refresh_diff()` | Snapshot + return last_diff |
| `page.on` / `page.on_event` | Subscribe |
| `page.wait_for_event` | Await one event |
| `page.events.history()` | Ring buffer |
| `page.watch(enabled=...)` | MutationObserver on/off |

## Modules

| Path | Role |
|------|------|
| `models/diff.py` | `Diff` + summary |
| `models/events.py` | `EventType`, `BrowserEvent` |
| `events/diffing.py` | `DiffEngine` |
| `events/bus.py` | `EventBus` |
| `events/monitor.py` | MutationObserver bridge |

## Tests

```bash
pytest tests/test_diff_engine.py tests/test_event_bus.py tests/test_events_page.py -q
```
