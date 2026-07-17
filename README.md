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

## Milestones & branches

Each milestone has a dedicated branch. Implement features on the milestone branch, then merge toward `master` / `dev`.

| Branch | Milestone | Focus |
|--------|-----------|--------|
| `milestone/m1-foundation` | M1 | Core API + Playwright; `open` / `click` / `type` / raw snapshot |
| `milestone/m2-semantic-dom` | M2 | Semantic DOM + AX merge, stable IDs, `snapshot()` JSON |
| `milestone/m3-diffs-events` | M3 | Incremental diffs & event streaming |
| `milestone/m4-vision-ocr` | M4 | Tesseract/OCR + vision APIs |
| `milestone/m5-network` | M5 | Network capture, wait_for_api, GraphQL basics |
| `milestone/m6-accessibility` | M6 | a11y polish, `get_by_role` / `get_by_label` |
| `milestone/m7-memory-planner` | M7 | Session memory, context summary, `plan()` |
| `milestone/m8-antibot` | M8 | Humanized mouse/keyboard, anti-fingerprint |
| `milestone/m9-multiagent` | M9 | Concurrent agents, event subscriptions |
| `milestone/m10-polish` | M10 | Tests, docs, optimization, security review |

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

### Minimal usage (M1 target API)

```python
from agent_browser import Browser

async def main():
    async with Browser(headless=True) as browser:
        page = await browser.new_page()
        await page.open("https://example.com")
        snap = await page.snapshot()
        print(snap.url, snap.title)
        # Later milestones:
        # btn = await page.find(role="button", text_contains="More")
        # await page.click(btn)

# asyncio.run(main())
```

### CLI

```bash
agent-browser --help
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
