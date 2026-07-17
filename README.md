# Agentic Browser

### The web, as an LLM wants to see it

**Stable refs · compact observations · outcome-verified actions · MCP for any agent host**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Version 0.4.0](https://img.shields.io/badge/version-0.4.0-brightgreen.svg)](./CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-118%20passed-success.svg)](#development)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey.svg)](./LICENSE)
[![MCP](https://img.shields.io/badge/MCP-ready-purple.svg)](./docs/mcp.md)

> Not another HTML scraper. A **real Chromium browser** controlled with **semantic tools** — so Claude, Cursor, LangGraph, or your own agent can **see, click, type, and verify** without drowning in 100k+ tokens of markup.

**Repo:** [github.com/applejuice093/Agentic-browser](https://github.com/applejuice093/Agentic-browser) · **Branch:** `dev`

---

## Why this exists

Traditional stacks hand the model **raw HTML** or brittle CSS. Agents need:

1. **Small, structured observations** (roles, labels, refs)  
2. **Actions that mean success** (URL/DOM outcomes, not “no exception”)  
3. **A way to plug into any host** (MCP + OpenAI/Anthropic tool schemas)

Agentic Browser is built for that loop.

```text
navigate → observe (~1–2k tokens) → click_text / type → outcome_verified?
         ↘ if page_gate = challenge → stop (don’t hallucinate)
```

---

## Highlights — measured positives

Numbers from live benchmarks on public sites (approx. tokens ≈ chars/4). Reproduce with scripts under `examples/`.

### Token efficiency (LLM feed)

| Scenario | Raw HTML → model | Our compact observation / structured feed | **Reduction** |
|----------|-----------------:|------------------------------------------:|--------------:|
| Quotes scrape (structured answers) | ~2.8k–6.2k | ~0.45k–1.3k | **~78–84% fewer tokens** |
| Rockstar GTA VI landing | ~**225,000** | ~**1,300** | **~99.4% fewer tokens** |
| GitHub `vercel/next.js` | ~**110,000** | ~**1,900** | **~98.3% fewer tokens** |

**Takeaway:** Dumping HTML into an LLM is the wrong default. **Observation mode is ~98–99% smaller** on heavy modern pages.

### Task quality

| Metric | Traditional HTTP + BS4 | Agentic Browser | Notes |
|--------|------------------------|-----------------|--------|
| Quote scrape field completeness | **100%** (with site CSS) | **100%** | Parity on friendly sites |
| Plain-text “LLM scrape” completeness | **0%** tags lost | **100%** via tools | Text dumps drop structure |
| Content signals on GitHub repo | **~70%** | **~80%** | Slight edge after JS + observe |
| Actionable element refs | **0** | **20–90+** per page | Only we can click by ref |
| GitHub “open Issues” (after v0.3.2) | N/A | **Verified** → URL `/issues` | Outcome-checked, not false-ok |
| Network / XHR visibility | **0%** | Full request log + GraphQL flags | Agent can wait on APIs |

### Product completeness

| Area | Coverage |
|------|----------|
| Milestone roadmap M1–M10 | **100%** of planned milestones delivered (plus agent-native v0.3–0.4) |
| Automated tests on `dev` | **118 passed** (full suite) |
| MCP tools for hosts | **10 tools** (navigate, observe, click, type, wait, find, network, …) |
| Observation token budget (default) | **~2,000** (configurable) |

### Positives at a glance

- **~98–99%** token cut vs raw HTML on complex landings (Rockstar, GitHub)  
- **~78–84%** token cut vs HTML for structured extract tasks  
- **100%** structured field parity with best-case CSS scrapers on demo sites  
- **Outcome verification** — `ok` only when post-conditions hold (e.g. `/issues` in URL)  
- **Scoped grounding** — nav-first find so PR/commit text doesn’t steal “Issues”  
- **Page gates** — `js_challenge` / captcha / login wall **detected and reported**  
- **MCP-ready** — Claude Desktop, Cursor, any MCP host  
- **OpenAI + Anthropic tool schemas** — `tools_as_openai()` / `tools_as_anthropic()`  
- Cookie/CMP dismiss, SPA settle budgets, stale-ref recovery, network intelligence  
- Privacy defaults: mask `Authorization` / cookies in network logs  

---

## Bottlenecks & negatives (no sugarcoating)

We measure these so you don’t ship blind.

| Issue | Reality | Impact |
|-------|---------|--------|
| **Latency** | Real browser is **~6–16× slower** than `httpx` on the same URL | Bad for high-QPS crawl; fine for agent steps |
| **Bot walls** | Reddit-class JS challenges: **both** HTTP and browser get **~17%** content signals | **Not a bypass tool** — we surface `page_gate` and stop |
| **SSR-only read** | On some marketing pages, plain HTTP already has the copy | Agent wins on **actions**, not always on pure read speed |
| **Full semantic snapshot** | Can be **larger** than HTML if you dump everything | Always use **`observe()`**, not full tree, for LLMs |
| **Speed vs design goal** | Sub-500 ms action latency is **not** met end-to-end on heavy SPAs | Dominated by page load + settle, not Python |
| **False success (historical)** | Pre-0.3.2 GitHub “Issues” click could report ok without navigating | **Fixed** with outcome verification + GitHub skill |
| **Skills coverage** | GitHub tab skill is first-class; other domains need packs | Extensible under `agent/skills/` |
| **Vision** | OCR optional; not in the default observe loop | Canvas-heavy UIs still weaker |

**Honest product line:**  
Best as an **LLM action + compact perception layer**.  
Not a replacement for bulk HTTP scraping, and not a captcha solver.

---

## Architecture

```text
┌──────────────────────────────────────────────────────┐
│  Claude · Cursor · LangGraph · OpenAI tool loop      │
└──────────────────────────┬───────────────────────────┘
                           │ MCP stdio  or  function tools
                           ▼
┌──────────────────────────────────────────────────────┐
│  agent-browser MCP  ·  tools_as_openai()             │
│  AgentSession: observe · click_text · wait · network │
└──────────────────────────┬───────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────┐
│  Semantic DOM · scoped grounding · outcomes · gates  │
│  Network monitor · memory · settle · overlay dismiss │
└──────────────────────────┬───────────────────────────┘
                           ▼
                 Playwright · Chromium
```

---

## Installation

### Requirements

- **Python 3.11+**
- Git  
- ~Windows / macOS / Linux  

### Library + dev

```bash
git clone https://github.com/applejuice093/Agentic-browser.git
cd Agentic-browser
git checkout dev

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -e ".[dev]"
playwright install chromium
pytest -q
```

### With MCP (Claude / Cursor)

```bash
pip install -e ".[mcp,dev]"
playwright install chromium
```

### Optional vision (local OCR)

```bash
pip install -e ".[vision]"
# Install system Tesseract; set TESSERACT_CMD on Windows
```

### Extras summary

| Extra | Install | Provides |
|-------|---------|----------|
| default | `pip install -e .` | Core browser + agent API |
| `mcp` | `pip install -e ".[mcp]"` | MCP server for hosts |
| `dev` | `pip install -e ".[dev]"` | pytest, ruff, mypy |
| `vision` | `pip install -e ".[vision]"` | Pillow + pytesseract |
| `all` | `pip install -e ".[all]"` | Everything |

---

## Add to your agent (3 ways)

### A) MCP — Claude Desktop / Cursor (**recommended**)

```bash
python -m agent_browser.mcp
# or
agent-browser-mcp
```

**Cursor** — `.cursor/mcp.json` (use **your** venv Python path):

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "C:\\A\\PROJECT\\Agentic Browser\\.venv\\Scripts\\python.exe",
      "args": ["-m", "agent_browser.mcp"],
      "env": {
        "AGENT_BROWSER_HEADLESS": "true",
        "AGENT_BROWSER_MAX_TOKENS": "2000",
        "AGENT_BROWSER_ALLOWED_HOSTS": "github.com,example.com,quotes.toscrape.com"
      }
    }
  }
}
```

**Claude Desktop** — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "C:\\A\\PROJECT\\Agentic Browser\\.venv\\Scripts\\python.exe",
      "args": ["-m", "agent_browser.mcp"],
      "env": { "AGENT_BROWSER_HEADLESS": "true" }
    }
  }
}
```

Full guide (env vars, system prompt, troubleshooting): **[`docs/mcp.md`](./docs/mcp.md)**

### B) Python library

```python
import asyncio
from agent_browser import Browser, tools_as_openai

async def main():
    async with Browser(headless=True) as browser:
        agent = await browser.open_agent("https://github.com/vercel/next.js")
        obs = await agent.observe(max_tokens=2000)
        if obs.page_gate not in (None, "open", "cookie_wall", "unknown"):
            print("Blocked:", obs.page_gate, obs.page_gate_hint)
            return
        result = await agent.click_text("Issues", scope="nav", intent="issues")
        print(result.ok, result.url_after, result.outcome_verified)

asyncio.run(main())
```

OpenAI / Anthropic tool schemas:

```python
from agent_browser import tools_as_openai, tools_as_anthropic
tools = tools_as_openai()       # Chat Completions
# tools = tools_as_anthropic()  # Messages API
```

### C) CLI

```bash
agent-browser version
agent-browser open https://example.com
agent-browser scrape https://example.com -o data/out.json
```

---

## Core concepts

| Concept | Meaning |
|---------|---------|
| **ref** | Stable integer id for click/type (from `observe`) |
| **Observation** | Compact LLM payload: interactive refs, headings, summary, gate, network hints |
| **ActionResult** | `ok`, `error_code`, `outcome_verified`, `url_after`, optional new observation |
| **page_gate** | `open` \| `js_challenge` \| `captcha` \| `login_wall` \| … |
| **scope** | `nav` / `main` / `form` — grounding region for find/click |

### MCP / tool surface

`browser_navigate` · `browser_observe` · `browser_click` · `browser_click_text` · `browser_type` · `browser_wait` · `browser_find` · `browser_network` · `browser_resync` · `browser_prepare`

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_BROWSER_HEADLESS` | `true` | Headless Chromium |
| `AGENT_BROWSER_MAX_TOKENS` | `2000` | Observation budget |
| `AGENT_BROWSER_DETAIL` | `normal` | `sparse` \| `normal` \| `full` |
| `AGENT_BROWSER_SETTLE_MS` | `8000` | SPA settle budget |
| `AGENT_BROWSER_ALLOWED_HOSTS` | _(all)_ | Comma-separated allowlist |
| `AGENT_BROWSER_DEFAULT_TIMEOUT_MS` | `30000` | Action timeout |
| `TESSERACT_CMD` | — | OCR binary path (vision extra) |

---

## Project layout

```text
src/agent_browser/
  browser.py / page.py / cli.py
  agent/          # AgentSession, MCP tools bridge, settle, overlays, grounding, outcomes, skills
  mcp/            # FastMCP stdio server
  observation/    # Compact observation builder
  semantic/ accessibility/ events/ network/ vision/ memory/ planning/
docs/
  mcp.md                 # Add to Claude / Cursor / custom agents
  USER_GUIDE.md
  agent-native-loop.md
  security.md
examples/
  agent_loop_demo.py
  openai_tool_agent.py
  mcp_config_cursor.json
  benchmark_hard_site.py
  compare_rockstar_vi.py
tests/                   # 118+ automated tests
```

---

## Development

```bash
git checkout dev
pip install -e ".[dev,mcp]"
playwright install chromium
pytest -q
ruff check src tests
```

| Doc | Topic |
|-----|--------|
| [`docs/mcp.md`](./docs/mcp.md) | **Install into your agent (MCP + tools)** |
| [`docs/USER_GUIDE.md`](./docs/USER_GUIDE.md) | Full product guide |
| [`docs/agent-native-loop.md`](./docs/agent-native-loop.md) | Observe / act / gates / skills |
| [`docs/security.md`](./docs/security.md) | Security notes |
| [`CHANGELOG.md`](./CHANGELOG.md) | Version history |
| [`deep-research-report.md`](./deep-research-report.md) | Original design research |

---

## Roadmap status

| Track | Status |
|-------|--------|
| M1–M10 foundation | **Done** |
| Agent-native loop (v0.3) | **Done** |
| Overlays / settle / recovery (v0.3.1) | **Done** |
| Grounding + outcomes + GitHub skill (v0.3.2) | **Done** |
| MCP host integration (v0.4.0) | **Done** |
| More domain skills, vision-in-loop, pool/scale | Next |

---


---

## License

MIT — see [LICENSE](./LICENSE).

---

<p align="center">
  <b>Small observations. Real clicks. Verified outcomes.</b><br/>
  <sub>Agentic Browser · built for LLMs that have to act on the web</sub>
</p>
