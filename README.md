# Agentic Browser

**AI Agent-First Browser** — a Python system that exposes the web as a continuous semantic “world model” for LLM agents, not raw HTML or pixels.

Agents query and act on pages via high-level concepts (objects, roles, actions) with stable element IDs, incremental diffs, accessibility merge, OCR/vision, network introspection, event streaming, planning/memory, and anti-bot protections.

> Design source: [`deep-research-report.md`](./deep-research-report.md)

## Goals

| Goal | Description |
|------|-------------|
| Rich semantic model | Pages as graphs of objects (role, text, state), not HTML tags |
| Resilient automation | ARIA/role+name locators; stable numeric element IDs |
| Efficient context | Compressed snapshots (target ≪ full DOM token cost) |
| Full interactivity | `click`, `type`, navigate, wait, JS via high-level Python API |
| Discoverability | Snapshots, semantic find, network inspector |
| Security & ethics | Session isolation, privacy-aware design, compliance hooks |

## Architecture (high level)

```
AI Agent (LLM)
    │ JSON-RPC / WebSocket / Python API
    ▼
Python Agent Browser API
    ├── Semantic DOM Engine
    ├── Accessibility / ARIA Engine
    ├── Vision / OCR Engine
    ├── Network Monitor
    ├── JS Execution (injected / QuickJS)
    ├── Planner & Memory
    ├── Anti-Bot / Fingerprint Handler
    └── Underlying Browser (Chromium/WebKit via Playwright)
```

## Project layout

```
.
├── deep-research-report.md   # Full design & roadmap
├── pyproject.toml
├── requirements.txt
├── src/agent_browser/        # Library package
│   ├── browser.py            # Browser session entry
│   ├── page.py               # Page API
│   ├── models/               # Pydantic data models
│   ├── semantic/             # Semantic DOM + stable IDs (M2)
│   ├── accessibility/        # AX tree merge & queries (M2/M6)
│   ├── events/               # Diffs & event streaming (M3)
│   ├── vision/               # OCR / vision (M4)
│   ├── network/              # Network / API intelligence (M5)
│   ├── memory/               # Session memory (M7)
│   ├── planning/             # Context & planner (M7)
│   ├── antibot/              # Humanized input (M8)
│   ├── multiagent/           # Multi-agent sessions (M9)
│   └── cli.py                # CLI entrypoint
├── tests/
├── examples/
└── docs/
```

## Status (v0.2.0)

| Milestone | Status | Focus |
|-----------|--------|--------|
| M1 | Done | Core API + Playwright |
| M2 | Done | Semantic DOM + stable IDs |
| M3 | Done | Diffs + event streaming |
| M4 | Done | OCR / vision hooks |
| M5 | Done | Network capture, wait_for_api, GraphQL |
| M6 | Done | `get_by_role` / `get_by_label` |
| M7 | Done | Memory, context, plan |
| M8 | Done | Humanized input |
| M9 | Done | Multi-agent sessions |
| M10 | Done | Docs, security, polish |

**User guide:** [`docs/USER_GUIDE.md`](./docs/USER_GUIDE.md) · **Add to your agent (MCP):** [`docs/mcp.md`](./docs/mcp.md) · **Agent loop:** [`docs/agent-native-loop.md`](./docs/agent-native-loop.md) · Changelog: [`CHANGELOG.md`](./CHANGELOG.md)

### Add to Claude / Cursor (MCP)

```bash
pip install -e ".[mcp]"
playwright install chromium
```

Point your host at:

```text
python -m agent_browser.mcp
# or: agent-browser-mcp
```

See full configs for **Cursor** and **Claude Desktop** in [`docs/mcp.md`](./docs/mcp.md).

### LLM agent loop (library)

```python
async with Browser() as browser:
    agent = await browser.open_agent("https://example.com")
    obs = await agent.observe(max_tokens=1500)   # compact refs, not full HTML
    result = await agent.click_text("More information", scope="any")
    # result.ok, result.error_code, result.observation
```

### Branches

Milestone branches `milestone/m1-foundation` … `milestone/m10-polish` track incremental work; `master` / `dev` hold the merged stack.

## Quick start

### Requirements

- Python 3.11+
- Git

### Install

```bash
# Clone
git clone https://github.com/applejuice093/Agentic-browser.git
cd Agentic-browser

# Virtualenv (recommended)
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -e ".[dev]"
playwright install chromium
```

### Minimal usage (M1 API)

```python
import asyncio
from agent_browser import Browser

async def main():
    async with Browser(headless=True) as browser:
        page = await browser.set_content(
            "<html><body>"
            "<label for='q'>Search</label>"
            "<input id='q' /><button>Go</button>"
            "</body></html>"
        )
        snap = await page.snapshot()
        q = await page.get_by_label("Search")
        await page.fill(q.id, "headphones")
        btn = await page.get_by_role("button", name="Go")
        await page.click(btn.id)
        print(await page.context(max_tokens=500, goal="search"))
        print(await page.plan("search products"))

asyncio.run(main())
```

### CLI

```bash
agent-browser version
agent-browser open https://example.com
agent-browser open https://example.com --raw-html --compact
```

## Development workflow

1. Check out the milestone branch for the work item, e.g.  
   `git checkout milestone/m1-foundation`
2. Implement against the design in `deep-research-report.md`
3. Add/adjust tests under `tests/`
4. Open a PR into `dev` (or `master` per team convention)

```bash
pytest
ruff check src tests
```

## Success metrics (from design)

- Task success ≥ 90% on common agent workflows  
- Action latency under ~500 ms in typical cases  
- Snapshot token budget on the order of a few thousand (not full HTML)  
- Low block/CAPTCHA failure rate with ethical, legitimate use  

## License

MIT — see repository license when published.

## Remote

https://github.com/applejuice093/Agentic-browser
