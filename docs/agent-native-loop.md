# Agent-native observation loop (v0.3)

**Branch:** `feature/agent-native-loop`

## Why

LLM agents need **cheap, stable, actionable** observations — not full HTML or fat DOM dumps.

## API

```python
from agent_browser import Browser, tools_as_openai

async with Browser() as browser:
    agent = await browser.open_agent("https://example.com")

    obs = await agent.observe(detail="normal", max_tokens=2000)
    # obs.interactive[].ref  →  click/type targets

    result = await agent.click(obs.interactive[0].ref)
    # result.ok, result.error_code, result.observation

    await agent.type(ref, "query", clear=True, submit=True)
    await agent.wait("api", value="/api/", timeout_ms=10000)
    await agent.resync()  # if refs look stale

    # LLM tool-calling
    await agent.call_tool("browser_click", {"ref": 12})
    tools = tools_as_openai()  # bind to your model
```

### Detail levels

| Level | Contents |
|-------|----------|
| `sparse` | Interactive only, short text, tiny |
| `normal` | Interactive + headings + network hints + diff |
| `full` | Large (debug); prefer resync rarely |

### Error codes

`element_not_found`, `element_stale`, `timeout`, `navigation_failed`, `network_timeout`, `page_closed`, …

### Tools

`browser_navigate`, `browser_observe`, `browser_click`, `browser_type`, `browser_wait`, `browser_find`, `browser_network`, `browser_resync`

## Files

- `agent/session.py` — AgentSession  
- `agent/tools.py` — tool schemas  
- `observation/compact.py` — token-budgeted builder  
- `models/observation.py` — Observation / ActionResult / ErrorCode  
