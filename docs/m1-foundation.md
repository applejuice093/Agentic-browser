# M1 — Foundation

**Branch:** `milestone/m1-foundation`  
**Goal:** Base browser API with Playwright integration, simple Python CLI, and basic `open` / `click` / `type` / raw DOM snapshot.

## Delivered

| Capability | API |
|------------|-----|
| Session lifecycle | `async with Browser() as browser`, `start()`, `stop()`, `is_started` |
| Pages | `new_page()`, `open(url)`, `set_content(html)` (offline) |
| Navigation | `page.open` / `goto`, `reload`, `go_back`, `go_forward` |
| Actions | `click`, `type`, `fill`, `press`, `select_option` |
| Snapshot | `snapshot()` → url, title, scroll, elements with stable `data-agent-id` |
| Raw DOM | `snapshot(include_raw_html=True)`, `content()` |
| Escape hatch | `evaluate`, `screenshot`, `playwright_page` |
| CLI | `agent-browser open <url>`, `agent-browser version` |
| Errors | `ElementNotFoundError`, `NavigationError`, `BrowserNotStartedError`, … |

## Target resolution (M1)

1. **Integer id** — from the latest `snapshot()` (`data-agent-id` in DOM).  
2. **Element model** — uses `element.id`.  
3. **CSS selector string** — e.g. `#submit-btn`, `text=Submit`.

## Example

```python
from agent_browser import Browser

async with Browser(headless=True) as browser:
    page = await browser.open("https://example.com")
    snap = await page.snapshot()
    # or offline:
    # page = await browser.set_content("<button id='b'>Go</button>")
    await page.click("#more-information")  # selector
    # await page.click(snap.elements[0].id)  # stable id after snapshot
```

## Tests

```bash
pytest tests/test_browser_page.py tests/test_cli.py tests/test_models.py -q
```

Integration tests use local HTML fixtures (`set_content`) — no external network required for the core suite.
