# Agent-native observation loop (v0.3.1)

**Branch:** `feature/agent-native-loop` · merged into `dev`

## Why

LLM agents need **cheap, stable, actionable** observations — not full HTML or fat DOM dumps.
Marketing SPAs also need **overlay dismissal** and **settled hydration** before the first look.

## Systems (bottleneck workarounds)

| Bottleneck | System |
|------------|--------|
| Cookie / CMP / privacy walls | `overlays.dismiss_overlays` (selectors + role + JS + hide fallback) |
| SPA hang on `networkidle` | `settle.settle_page` budgeted wait (domcontentloaded → capped networkidle) |
| Lazy content below fold | optional scroll probe during prepare |
| Noisy CMP headings | `is_noise_text` filter in compact observation |
| Fat HTML / fat trees | token-budgeted `build_observation` + `summary` field |
| Stale refs after re-render | auto resync + optional `text_hint` re-find on click/type |
| Analytics spam in network | filter sentry/gtm/onetrust from observation network hints |

## API

```python
from agent_browser import Browser, tools_as_openai

async with Browser() as browser:
    # prepare() runs automatically: settle + dismiss cookies
    agent = await browser.open_agent("https://www.rockstargames.com/VI")

    obs = await agent.observe(max_tokens=2000)
    print(obs.summary)           # high-signal one-liner
    print(obs.interactive[0])  # {ref, role, text, href, ...}

    result = await agent.click(ref, text_hint="Pre-Order")  # recovery hint
    await agent.resync()  # nuclear option

    tools = tools_as_openai()
    await agent.call_tool("browser_prepare", {})
```

### Detail levels

| Level | Contents |
|-------|----------|
| `sparse` | Interactive only, short text, tiny |
| `normal` | Interactive + clean headings + network hints + diff + summary |
| `full` | Large (debug); prefer resync rarely |

### Error codes

`element_not_found`, `element_stale`, `timeout`, `navigation_failed`, `network_timeout`, `page_closed`, …

### Tools

`browser_navigate`, `browser_observe`, `browser_click`, `browser_type`, `browser_wait`, `browser_find`, `browser_network`, `browser_resync`, `browser_prepare`

## Files

- `agent/session.py` — AgentSession  
- `agent/overlays.py` — consent / modal dismiss  
- `agent/settle.py` — budgeted SPA settle  
- `agent/recovery.py` — stale-ref helpers  
- `agent/tools.py` — tool schemas  
- `observation/compact.py` — token-budgeted builder  
- `models/observation.py` — Observation / ActionResult / ErrorCode  
