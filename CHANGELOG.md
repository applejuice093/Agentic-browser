# Changelog

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
