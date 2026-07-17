# Changelog

## 0.4.0 — MCP server for Claude / Cursor / any MCP host

### Added

- **`python -m agent_browser.mcp`** / **`agent-browser-mcp`** FastMCP stdio server
- **`McpSessionManager`** — shared Browser + AgentSession for tool hosts
- Host env: `AGENT_BROWSER_HEADLESS`, `MAX_TOKENS`, `ALLOWED_HOSTS`, …
- **`tools_as_anthropic()`** export
- User guide: **`docs/mcp.md`** (Cursor, Claude Desktop, OpenAI tool loop)
- Example configs: `examples/mcp_config_cursor.json`, `examples/openai_tool_agent.py`

## 0.3.2 — Grounding, outcome verification, challenge gates

### Research-backed systems

- **Outcome verification** (BrowserGym-style): `ok` only if post-conditions hold (URL/text/selector), not merely exception-free
- **Scoped grounding**: nav/main/form ranking; penalize commit/PR body false matches (dual-grounding inspiration)
- **Page gate classifier**: js_challenge / captcha / login_wall / rate_limit — surface to LLM, no bypass claims
- **GitHub skill pack**: deterministic tab URLs for Issues/PRs/Actions when on a repo
- Tools: `browser_click_text`, click-by-text with `scope=nav`

### Proven on GitHub next.js

- Before: Issues click `ok` but stayed on repo URL (false success)
- After: lands on `/issues` with `outcome_verified=true`

## 0.3.1 — Production agent systems (overlays, settle, recovery)

### Added

- **Overlay dismisser** — OneTrust/Cookiebot/role/JS + hide fallback
- **Budgeted SPA settle** — no infinite networkidle hangs
- **Noise filtering** — strip CMP/privacy headings from observations
- **Observation.summary** — one-line high-signal page summary for LLMs
- **Stale-ref recovery** — resync + optional text_hint on click/type
- **scroll_into_view** before click; analytics noise filtered from network hints
- Tool: `browser_prepare`

## 0.3.0 — Agent-native observation loop

### Added

- **AgentSession** — `observe` / `click` / `type` / `wait` / `resync` / `call_tool`
- **Observation** + **ActionResult** schemas (versioned, compact, error codes)
- Token-budgeted compact builder (`sparse` | `normal` | `full`)
- Diff + network hints on each observation
- OpenAI-style tool definitions (`tools_as_openai()`)
- `page.as_agent()`, `browser.open_agent()`, `page.observe()`
- Docs: `docs/agent-native-loop.md`, example `examples/agent_loop_demo.py`

## 0.2.1 — M5 network intelligence

### Added

- **M5** Network capture, `wait_for_api`, GraphQL detection, `route` helper
- Full **User Guide** (`docs/USER_GUIDE.md`)

## 0.2.0 — M1–M10 foundation stack

### Added

- **M1** Browser/Page Playwright API, CLI, offline fixtures
- **M2** Semantic DOM, stable IDs, `find` / tree links
- **M3** Diffs, event bus, MutationObserver `watch`
- **M4** Vision OCR (`get_text_in_screenshot`), UI detection hooks
- **M6** `get_by_role` / `get_by_label` / placeholder / text / test id
- **M7** Session memory, `context()`, rule-based `plan()`
- **M8** Humanized mouse paths and typing delays
- **M9** Multi-agent sessions with per-agent subscriptions
- **M10** Docs index, security notes, performance guidance
