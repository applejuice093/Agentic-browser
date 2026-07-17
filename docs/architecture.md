# Architecture overview

See the design report for full diagrams: [deep-research-report.md](../deep-research-report.md).

## Layers

1. **Agent surface** — Python API (`Browser`, `Page`) and optional JSON-RPC/WebSocket (future).
2. **Intelligence** — Semantic DOM, accessibility, vision, network, planner, anti-bot.
3. **Browser backend** — Playwright-controlled Chromium / Firefox / WebKit.

## Data flow (M1+)

```
Agent → Page.open(url)
     → Playwright navigation
     → Page.snapshot()  # injects data-agent-id, extracts interactive nodes
     → Snapshot (Pydantic) → agent reasoning
     → Page.click(element_id | selector)
```

## Module map

| Module | Responsibility | Milestone |
|--------|----------------|-----------|
| `agent_browser.browser` | Session / Playwright lifecycle | M1 |
| `agent_browser.page` | Actions + snapshots | M1 |
| `agent_browser.models` | Element, Snapshot, Diff, Event | M1 |
| `agent_browser.semantic` | Object model + stable IDs | M2 |
| `agent_browser.accessibility` | AX tree merge | M2/M6 |
| `agent_browser.events` | Diffs + streaming | M3 |
| `agent_browser.vision` | OCR / vision | M4 |
| `agent_browser.network` | API capture | M5 |
| `agent_browser.memory` | Session history | M7 |
| `agent_browser.planning` | Context + plan | M7 |
| `agent_browser.antibot` | Humanized input | M8 |
| `agent_browser.multiagent` | Multi-agent sessions | M9 |

## Privacy & compliance defaults

- Session isolation via Playwright browser contexts
- `respect_robots_txt` config flag (default true)
- Prefer local OCR over cloud (M4)
- Mask sensitive fields in action logs (M7+)
