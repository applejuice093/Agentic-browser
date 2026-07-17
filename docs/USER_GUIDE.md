# Agentic Browser — User Guide

**Version:** 0.2.x · **Package:** `agent-browser`  
**Repo:** https://github.com/applejuice093/Agentic-browser

This guide shows how to install and use the AI agent-first browser: semantic snapshots, finders, events, network intelligence, vision, memory, and multi-agent sessions.

---

## 1. Install

### Requirements

- Python **3.11+**
- Git
- Windows / macOS / Linux

### Setup

```bash
git clone https://github.com/applejuice093/Agentic-browser.git
cd Agentic-browser

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -e ".[dev]"
playwright install chromium
```

### Optional extras

```bash
# OCR / vision (needs system Tesseract for real OCR)
pip install -e ".[vision]"
# Windows: install Tesseract and set TESSERACT_CMD
# Debian: sudo apt install tesseract-ocr
```

### Verify

```bash
agent-browser version
pytest -q
```

---

## 2. Core concepts

| Concept | Meaning |
|---------|---------|
| **Browser** | One Playwright session (context, memory, optional multi-agent) |
| **Page** | One tab with actions, snapshot, events, network |
| **Snapshot** | Semantic list of elements (role, name, stable `id`, tree links) |
| **Stable ID** | Integer handle for click/fill after `snapshot()`; stamped as `data-agent-id` |
| **Diff** | What changed since the previous snapshot (`page.last_diff`) |
| **Events** | Stream of navigation, clicks, mutations, API calls, etc. |

Always prefer **stable ids** or **get_by_role / get_by_label** over brittle CSS when writing agents.

---

## 3. Quick start

```python
import asyncio
from agent_browser import Browser

async def main():
    async with Browser(headless=True) as browser:
        page = await browser.set_content(
            """
            <html><body>
              <label for="q">Search</label>
              <input id="q" />
              <button type="button">Go</button>
            </body></html>
            """
        )
        q = await page.get_by_label("Search")
        await page.fill(q.id, "headphones")
        btn = await page.get_by_role("button", name="Go")
        await page.click(btn.id)
        print(await page.context(max_tokens=400, goal="search products"))

asyncio.run(main())
```

Open a real URL:

```python
page = await browser.open("https://example.com")
snap = await page.snapshot()
print(snap.title, len(snap.elements))
```

CLI:

```bash
agent-browser open https://example.com
agent-browser open https://example.com --raw-html --compact
```

---

## 4. Navigation & actions

```python
await page.goto("https://example.com")
await page.reload()
await page.go_back()

await page.click(selector_or_id_or_element)
await page.fill(target, "text")
await page.type(target, "text", clear=True)   # keystrokes
await page.press(target, "Enter")
await page.select_option(target, "value")

await page.wait_for_selector("#ready")
await page.wait_for_network_idle()
html = await page.content()
png = await page.screenshot()
```

Targets may be:

1. **int** — stable id from the latest snapshot  
2. **Element** — model from snapshot / finders  
3. **str** — CSS / Playwright selector (`#id`, `text=Submit`)

---

## 5. Semantic snapshot & find (M2)

```python
snap = await page.snapshot()
# snap.url, snap.title, snap.elements[], snap.scroll_position
# optional: include_raw_html=True

btn = await page.find(role="button", text_contains="Checkout")
await page.click(btn.id)

all_links = await page.find_all(role="link")
```

IDs stay stable across in-page updates until you navigate or `set_content`.

---

## 6. Accessibility finders (M6)

```python
email = await page.get_by_label("Email")
await page.fill(email.id, "user@example.com")

submit = await page.get_by_role("button", name="Sign in", exact=False)
await page.click(submit.id)

await page.get_by_placeholder("Search…")
await page.get_by_text("Forgot password")
await page.get_by_test_id("checkout-btn")
```

Also: `get_all_by_role`, `get_all_by_label`.

---

## 7. Diffs & events (M3)

```python
page.on(lambda e: print(e.event, e.data))

await page.snapshot()          # baseline
await page.click("#add")
await page.snapshot()
print(page.last_diff.summary())  # added / removed / changed counts

# Live DOM watching
await page.watch(enabled=True, debounce_ms=100, auto_snapshot=True)
# ... page mutates ...
await page.wait_for_event("mutation", timeout=5)
await page.watch(enabled=False)

# History
page.events.history(event_type="element_clicked")
```

Useful event types: `navigation`, `element_clicked`, `element_added`, `text_changed`, `page_changed`, `mutation`, `api_call`, `network_error`.

---

## 8. Network intelligence (M5)

### Capture

Network monitoring attaches automatically on `goto` / `set_content` / first network API use. It logs XHR/fetch and API-like URLs.

```python
# After user/agent actions that trigger APIs:
calls = page.network_requests(filter="api")
for c in calls:
    print(c["method"], c["url"], c["status"])

# Full models (headers, body, GraphQL flags)
for req in page.list_network_requests(filter="**/api/**"):
    print(req.method, req.url, req.response_status)
    print(req.response_body[:200] if req.response_body else None)
```

### Wait for an API

```python
await page.click("#checkout")
req = await page.wait_for_api("/api/cart", timeout_ms=15_000)
# optional: method="POST", status=200
assert req.response_status == 200
```

Patterns:

| Pattern | Meaning |
|---------|---------|
| `/api/cart` | Substring |
| `**/api/**` | Glob |
| `re:cart\\?id=\\d+` | Regex (`re:` prefix) |

### Mock / intercept

```python
await page.route("**/api/cart**", fulfill_json={"items": []})
# or custom:
# await page.route("**/api/**", handler=my_async_route_handler)
await page.unroute("**/api/cart**")
```

### GraphQL

```python
gql = page.list_network_requests(graphql_only=True)
for r in gql:
    print(r.graphql_operation, r.graphql_query_name, r.url)
```

### Privacy

- `Authorization`, `Cookie`, and similar headers are stored as `***`
- Response bodies are capped (default ~64KB); `response_body_truncated` marks cuts
- Clear when done: `page.clear_network_log()`

### Events

```python
page.on_event("api_call", lambda e: print("API", e.data))
page.on_event("network_error", lambda e: print("ERR", e.data))
```

---

## 9. Vision / OCR (M4)

```python
# Requires: pip install 'agent-browser[vision]' + Tesseract binary
regions = await page.get_text_in_screenshot()
# [{x,y,width,height,text,confidence}, ...]

text = await page.ocr_text()
await page.ocr_element("#captcha-or-canvas")
detections = await page.detect_ui()  # heuristic boxes (Pillow)
```

OCR is **on-demand** (not every navigation). Prefer local Tesseract for privacy.

---

## 10. Memory, context & planning (M7)

```python
browser.memory.set("shipping_address", "123 Main St")
await page.fill("#email", "a@b.c")  # actions logged

ctx = await page.context(max_tokens=1000, goal="complete checkout")
# ranked elements + forms/buttons under a token budget

plan = await page.plan("complete checkout")
# list of rule-based steps + suggested element ids

print(page.memory_summary())  # secrets masked (password, token, …)
```

Optional SQLite:

```python
from agent_browser import MemoryStore, Browser
mem = MemoryStore("sess-1", db_path="data/memory.db")
async with Browser(memory=mem) as browser:
    ...
```

---

## 11. Humanized input (M8)

```python
page.set_humanize(True)
await page.click("#buy")           # curved mouse path + delay
await page.type("#q", "hello")     # per-key delays

# Or via config / env AGENT_BROWSER_HUMANIZE=true
async with Browser(humanize=True) as browser:
    ...
```

**Ethics:** only on sessions you are authorized to automate. Not a CAPTCHA solver. See `docs/m8-antibot.md`.

---

## 12. Multi-agent (M9)

```python
async with Browser() as browser:
    page = await browser.set_content(html)
    session = browser.create_multi_agent_session()
    session.bind_page(page)

    nav = session.attach("navigator", role="navigator")
    form = session.attach("filler", role="input")

    nav.subscribe(lambda e: print("nav", e.event), event_type="navigation")
    form.subscribe(lambda e: print("all", e.event))

    async def fill():
        await page.fill("#email", "a@b.c")

    await form.run(fill())  # holds session lock
    await session.close()
```

---

## 13. Configuration

Environment variables (prefix `AGENT_BROWSER_`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `HEADLESS` | `true` | Headless browser |
| `BROWSER_TYPE` | `chromium` | chromium / firefox / webkit |
| `DEFAULT_TIMEOUT_MS` | `30000` | Action timeout |
| `HUMANIZE` | `false` | Enable humanized input |
| `TESSERACT_CMD` | — | Path to tesseract.exe |

```python
from agent_browser import Browser, BrowserConfig
cfg = BrowserConfig(headless=True, humanize=False, default_timeout_ms=20_000)
async with Browser(config=cfg) as browser:
    ...
```

---

## 14. Error types

| Exception | When |
|-----------|------|
| `ElementNotFoundError` | click/fill/type target missing |
| `NavigationError` | goto / set_content failed |
| `SnapshotError` | snapshot failed |
| `NetworkTimeoutError` | `wait_for_api` timed out |
| `VisionDependencyError` | OCR extras / Tesseract missing |
| `BrowserNotStartedError` | operation before start |

---

## 15. Performance tips

1. One `snapshot()` then many `get_by_*` / `find(..., refresh=False)`.
2. Call OCR only when the DOM lacks text (canvas/images).
3. `watch(auto_snapshot=False)` if you only need mutation pings.
4. Disable humanize for load tests.
5. Filter network logs; clear between scenarios.

---

## 16. Security & compliance

- Isolate sessions (`Browser` per agent user).
- Do not log `snapshot(include_raw_html=True)` with PII in shared logs.
- Network capture may include API payloads — treat as sensitive.
- Honor site terms, robots.txt policy, and user consent.
- Details: [`security.md`](./security.md)

---

## 17. Milestone docs

| Doc | Topic |
|-----|--------|
| [m1-foundation.md](./m1-foundation.md) | Browser/Page basics |
| [m2-semantic-dom.md](./m2-semantic-dom.md) | Semantic tree + IDs |
| [m3-diffs-events.md](./m3-diffs-events.md) | Diffs & events |
| [m4-vision-ocr.md](./m4-vision-ocr.md) | OCR |
| [m5-network.md](./m5-network.md) | Network intelligence |
| [m6-accessibility.md](./m6-accessibility.md) | a11y finders |
| [m7-memory-planner.md](./m7-memory-planner.md) | Memory & plan |
| [m8-antibot.md](./m8-antibot.md) | Humanize ethics |
| [m9-multiagent.md](./m9-multiagent.md) | Multi-agent |
| [m10-polish.md](./m10-polish.md) | Release notes |

Design source: [`../deep-research-report.md`](../deep-research-report.md)

---

## 18. Add agent-browser to Claude / Cursor / your agent

**Full guide:** [`mcp.md`](./mcp.md)

```bash
pip install -e ".[mcp]"
playwright install chromium
```

| Method | Use |
|--------|-----|
| MCP | `python -m agent_browser.mcp` in Cursor / Claude Desktop config |
| Python tools | `tools_as_openai()` / `tools_as_anthropic()` + `AgentSession.call_tool` |
| CLI | `agent-browser open` / `scrape` |

## 19. LLM agent loop (recommended)

Prefer **AgentSession** over dumping HTML or full snapshots into the model:

```python
from agent_browser import Browser, tools_as_openai

async with Browser(headless=True) as browser:
    agent = await browser.open_agent("https://example.com", max_tokens=2000)
    obs = await agent.observe(detail="normal")
    # obs.interactive = [{ref, role, name, text, href}, ...]

    result = await agent.click(some_ref)
    if not result.ok:
        print(result.error_code, result.error_message)
        await agent.resync()

    await agent.type(email_ref, "a@b.c", clear=True)
    await agent.wait("networkidle")

    # Bind tools to your LLM
    tools = tools_as_openai()
    await agent.call_tool("browser_find", {"role": "button", "text": "Next"})
```

Details: [`agent-native-loop.md`](./agent-native-loop.md).

## 20. Scraping data with the agent browser

This product is an **agent browser**, not a classic HTML parser. Prefer:

1. `open` / `snapshot` — semantic world model  
2. `get_by_role` / `find` — locate controls without brittle CSS  
3. `evaluate` — small in-page extractors when the DOM pattern is known  
4. `network_requests` / `wait_for_api` — capture JSON APIs behind the UI  
5. `context` / `plan` — feed structured state to an LLM agent  

### One-shot scrape helper

```python
from agent_browser import scrape_url
import asyncio, json

data = asyncio.run(scrape_url("https://example.com"))
print(json.dumps(data["headings"], indent=2))
print(data["counts"])
```

### Quotes demo (multi-page)

```bash
python examples/agent_scrape.py
python examples/agent_scrape.py --pages 2 --out data/scrape_result.json
python examples/agent_scrape.py --url https://books.toscrape.com --out data/books.json
```

Uses Playwright under the hood with **stable element IDs** to click “Next”,
then exports JSON for agents or pipelines.

**Legal note:** only scrape sites you are allowed to access; respect robots.txt
and terms of service. Prefer user-owned sessions for authenticated data.

## 21. Examples

```bash
python examples/agent_loop_demo.py
python examples/openai_tool_agent.py
python -m agent_browser.mcp   # MCP stdio (for hosts)
python examples/basic_open.py
python examples/agent_scrape.py --pages 2
python examples/benchmark_hard_site.py
```
