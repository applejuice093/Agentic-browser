# Add agent-browser to your LLM agent

This guide shows how to connect **agent-browser** to coding agents and LLM hosts.

| Integration | Best for | Effort |
|-------------|----------|--------|
| **MCP server** (recommended) | Claude Desktop, Cursor, any MCP host | Config only |
| **Python library + tools** | LangGraph, custom OpenAI/Anthropic loops | Few lines of code |
| **CLI** | Scripts, smoke tests | Terminal |

Core rule for models: **use compact tools** (`browser_observe`, `browser_click_text`) — never dump full HTML into context.

---

## 1. Install

**PyPI** (package name `agentic-browser`):

```bash
pip install "agentic-browser[mcp]"
playwright install chromium
```

**From source:**

```bash
git clone https://github.com/applejuice093/Agentic-browser.git
cd Agentic-browser

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -e ".[mcp,dev]"
playwright install chromium
```

Or from source with MCP extras only:

```bash
pip install -e ".[mcp]"
playwright install chromium
```

Verify:

```bash
agent-browser version
python -c "from agent_browser.mcp.server import create_mcp_server; create_mcp_server(); print('mcp ok')"
```

---

## 2. MCP (recommended) — Claude Desktop, Cursor, etc.

The MCP server is a thin process that maps tools → `AgentSession.call_tool()`.

### Start command

```bash
# equivalent:
python -m agent_browser.mcp
agent-browser-mcp
```

Hosts spawn this for you via config (stdio).

### Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `AGENT_BROWSER_HEADLESS` | `true` | Headless Chromium |
| `AGENT_BROWSER_MAX_TOKENS` | `2000` | Observation token budget |
| `AGENT_BROWSER_DETAIL` | `normal` | `sparse` \| `normal` \| `full` |
| `AGENT_BROWSER_SETTLE_MS` | `8000` | SPA settle budget after navigate |
| `AGENT_BROWSER_DEFAULT_TIMEOUT_MS` | `30000` | Playwright timeout |
| `AGENT_BROWSER_ALLOWED_HOSTS` | _(empty = all)_ | Comma list, e.g. `github.com,example.com` |

### Cursor

Create or edit **Cursor MCP config** (project or global).

**Project:** `.cursor/mcp.json`

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

On macOS/Linux use your venv python path:

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "/path/to/Agentic-browser/.venv/bin/python",
      "args": ["-m", "agent_browser.mcp"],
      "env": {
        "AGENT_BROWSER_HEADLESS": "true"
      }
    }
  }
}
```

Restart Cursor → enable the **agent-browser** MCP server → tools appear for the agent.

### Claude Desktop

Edit Claude Desktop config:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "C:\\A\\PROJECT\\Agentic Browser\\.venv\\Scripts\\python.exe",
      "args": ["-m", "agent_browser.mcp"],
      "env": {
        "AGENT_BROWSER_HEADLESS": "true",
        "AGENT_BROWSER_MAX_TOKENS": "2000"
      }
    }
  }
}
```

Restart Claude Desktop. Confirm tools under MCP / agent-browser.

### Claude Code / other MCP hosts

Same pattern: `command` = Python with package installed, `args` = `["-m", "agent_browser.mcp"]`.

### Tools the host will see

| Tool | Purpose |
|------|---------|
| `browser_navigate` | Open URL |
| `browser_observe` | Compact page state (refs, summary, `page_gate`) |
| `browser_click` | Click by `ref` or `text` |
| `browser_click_text` | Nav-scoped text click + outcome check |
| `browser_type` | Type into ref |
| `browser_wait` | timeout / selector / url / text / api / networkidle |
| `browser_find` | Scoped find (`scope=nav` for tabs) |
| `browser_network` | Recent API/XHR summaries |
| `browser_resync` | Recover after stale refs |
| `browser_prepare` | Settle SPA + dismiss cookies |

### Suggested agent system prompt (MCP / tools)

```text
You control a real browser via agent-browser tools.
1) browser_navigate then browser_observe.
2) If page_gate is js_challenge, captcha, or blocked — stop and tell the user; do not invent page content.
3) Prefer browser_click_text with scope=nav for site tabs (e.g. Issues on GitHub).
4) Treat ok=false / outcome_not_met as failure; resync or try another strategy.
5) Never request full HTML; use observe (max ~2000 tokens).
```

---

## 3. Python agent (LangGraph / custom loop)

Use the library directly when you own the agent runtime.

```python
import asyncio
import json
from agent_browser import Browser, tools_as_openai, tools_as_anthropic

async def run_agent_step():
    async with Browser(headless=True) as browser:
        agent = await browser.open_agent("https://github.com/vercel/next.js")

        # 1) Observe
        obs = await agent.observe(max_tokens=2000)
        print(obs.summary, obs.page_gate)

        # 2) Act with outcome verification
        result = await agent.click_text("Issues", scope="nav", intent="issues")
        print(result.ok, result.url_after, result.outcome_verified)

        # 3) Or OpenAI-style tool dispatch
        tools = tools_as_openai()  # pass to chat.completions
        # anthropic: tools_as_anthropic()

        out = await agent.call_tool(
            "browser_find",
            {"role": "link", "text": "Pull requests", "scope": "nav"},
        )
        print(json.dumps(out, indent=2)[:500])

asyncio.run(run_agent_step())
```

### OpenAI tool loop sketch

```python
from openai import OpenAI
from agent_browser import Browser, tools_as_openai

client = OpenAI()
tools = tools_as_openai()

async def tool_loop(user_goal: str):
    async with Browser() as browser:
        agent = await browser.open_agent("about:blank", settle=False)
        messages = [
            {"role": "system", "content": "Use browser_* tools. Observe before acting."},
            {"role": "user", "content": user_goal},
        ]
        for _ in range(12):
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
            )
            msg = resp.choices[0].message
            messages.append(msg)
            if not msg.tool_calls:
                return msg.content
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                result = await agent.call_tool(name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })
```

(Same idea with Anthropic `tools=` + `tools_as_anthropic()`.)

---

## 4. CLI (no LLM)

```bash
agent-browser open https://example.com
agent-browser scrape https://example.com -o out.json
```

Useful to validate network/Playwright before wiring an agent.

---

## 5. Safety for multi-user / demos

```bash
# Only allow specific hosts (MCP env)
set AGENT_BROWSER_ALLOWED_HOSTS=github.com,docs.python.org
```

- Prefer **headless** in shared machines.
- Do not log full `snapshot(include_raw_html=True)` with secrets.
- On `page_gate` ∈ {`js_challenge`,`captcha`,`soft_block`} → stop; do not retry loops.

---

## 6. Typical agent workflow

```
browser_navigate(url)
       ↓
browser_observe  →  check page_gate + summary + interactive[].ref
       ↓
browser_find / browser_click_text  (scope=nav for tabs)
       ↓
if ok && outcome_verified → continue
if outcome_not_met / challenge → resync or abort
       ↓
browser_network  when data is in XHR/API
```

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| MCP tools missing | Check Python path in host config; reinstall `pip install -e ".[mcp]"` |
| Browser not found | `playwright install chromium` |
| Empty page / cookie wall | Call `browser_prepare` or rely on auto-settle in `open_agent` |
| False Issues click (old behavior) | Use `browser_click_text` / `scope=nav` + intent (v0.3.2+) |
| Host can't start server | Run `python -m agent_browser.mcp` manually; fix import errors |
| Blocked host | Remove from allowlist or clear `AGENT_BROWSER_ALLOWED_HOSTS` |

---

## 8. Architecture (for implementers)

```
LLM host  --MCP stdio-->  agent_browser.mcp.server
                              │
                              ▼
                        McpSessionManager
                              │
                              ▼
                        AgentSession.call_tool
                              │
                              ▼
                        Playwright Browser / Page
```

- **Engine:** `agent_browser` library  
- **Facade:** MCP (this doc)  
- **Schema:** `TOOL_DEFINITIONS` / `tools_as_openai()` / `tools_as_anthropic()`  

---

## 9. Quick checklist for “my agent”

- [ ] `pip install -e ".[mcp]"` + `playwright install chromium`  
- [ ] MCP config points at **venv Python** + `-m agent_browser.mcp`  
- [ ] Optional allowlist for demos  
- [ ] System prompt: observe → gate check → scoped click → verify `ok`  
- [ ] Smoke: navigate to `https://example.com` → observe → see title/refs  

For deeper API: [agent-native-loop.md](./agent-native-loop.md) · [USER_GUIDE.md](./USER_GUIDE.md)
