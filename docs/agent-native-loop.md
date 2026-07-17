# Agent-native observation loop (v0.3.2)

**Branch:** `dev`

## Why

LLM agents need **cheap, stable, actionable** observations — not full HTML or fat DOM dumps.
Marketing SPAs need **overlay dismissal** and **settled hydration**. Dense sites (GitHub) need
**scoped grounding** and **outcome verification** so “ok” means the task succeeded.

Research touchstones: BrowserGym action errors + AX grounding; dual grounding / exact labels;
web-agent surveys on environment dynamics and blocked states (detect, don’t hallucinate content).

## Systems (bottleneck workarounds)

| Bottleneck | System |
|------------|--------|
| Cookie / CMP / privacy walls | `overlays.dismiss_overlays` |
| SPA hang on `networkidle` | `settle.settle_page` budgeted wait |
| Lazy content below fold | scroll probe during prepare |
| Noisy CMP headings | `is_noise_text` filter |
| Fat HTML / fat trees | token-budgeted `build_observation` + `summary` |
| Stale refs after re-render | resync + `text_hint` re-find |
| Analytics spam in network | filter sentry/gtm/onetrust |
| False-positive clicks | **outcome verification** (`outcome.py`) |
| Wrong element (PR body “issues”) | **scoped grounding** `scope=nav` (`grounding.py`) |
| Bot walls / JS challenges | **page_gate** classifier (`challenge.py`) — no bypass |
| GitHub tab navigation | **skill**: direct `/issues` `/pulls` URLs |

## API

```python
from agent_browser import Browser, tools_as_openai

async with Browser() as browser:
    agent = await browser.open_agent("https://github.com/vercel/next.js")

    obs = await agent.observe(max_tokens=2000)
    if obs.page_gate not in (None, "open", "cookie_wall", "unknown"):
        print("blocked:", obs.page_gate, obs.page_gate_hint)
    else:
        # Outcome-verified: ok only if URL contains /issues
        result = await agent.click_text("Issues", scope="nav", intent="issues")
        assert result.ok and "/issues" in result.url_after

    tools = tools_as_openai()
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
