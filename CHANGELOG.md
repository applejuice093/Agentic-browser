# Changelog

## Unreleased — 2026-11-03 hardening

### Fixes

- MCP server starts with `mcp` 2.x (`MCPServer`), still falls back to 1.x `FastMCP`
- MCP: blocked or malformed `browser_navigate` URLs return `blocked` / `invalid_args`
  results instead of raising, and no browser is launched for them
- MCP allowlist: only http(s) when set; entries like `https://github.com/` or
  `github.com:443` are normalised; trailing-dot hosts match
- MCP env settings (`MAX_TOKENS`, `SETTLE_MS`, `DETAIL`) validated with clear errors
- `MemoryStore`: SQLite connections are closed; reopening a session restores
  actions, URLs and forms; non-JSON values (datetime, Path) no longer crash
- `HumanizedInput`: inverted ranges rejected; click points stay inside tiny boxes
- `BrowserConfig`: humanize min delay may not exceed the max
- Scrape: only `h1`-`h6` count as headings (not `<header>`, `<hr>`, `<html>`)
- CLI: `--timeout` must be a non-negative integer; Ctrl+C exits 130 without a traceback
- Install hints use the `agentic-browser` package name

### Tests

- New `test_memory_store.py` and `test_scrape.py`; MCP tool list checked against
  `TOOL_DEFINITIONS`; allowlist, env, CLI timeout and humanize edge cases

## Unreleased — 2026-10-15 polish

### Docs & packaging

- README: default branch `main`, portable MCP config example, docs index link
- `requirements.txt` aligned with `pyproject.toml` extras (`mcp`, `pre-commit`)
- `.gitignore`: Playwright test artifacts + `coverage.xml`
- Added `Makefile`, `CONTRIBUTING.md`, and `docs/README.md` index
- Examples: shebangs, `.env.example` pointers, correct `agentic-browser[vision]` install name
- Milestone docs point new work at `main`

### API / code

- `BrowserConfig` field descriptions for all settings
- Public exports: `TimeoutError`, `BrowserAlreadyStartedError`
- CLI: `Literal` browser types; observation package re-exports helpers

### Tests

- Expanded `test_config.py` (env, validation, overrides)
- Added `test_exceptions.py` and `test_observation_compact.py` (no Playwright)


## 0.4.0 — MCP server for Claude / Cursor / any MCP host

### Packaging

- PyPI project name: **`agentic-browser`** (`pip install agentic-browser`)
- Import path and CLI unchanged: `agent_browser`, `agent-browser`, `agent-browser-mcp`
- Name `agent-browser` was unavailable / too similar on PyPI

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
