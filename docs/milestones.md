# Implementation milestones

Source: [deep-research-report.md](../deep-research-report.md) — Implementation Roadmap.

Each milestone has a **git branch**. Work on the branch for the active milestone; merge into `dev` when ready.

| Branch | ID | Feature | PM | Package area |
|--------|----|---------|----|--------------|
| `milestone/m1-foundation` | M1 | Core API + Browser integration | 3 | `browser.py`, `page.py`, `cli.py` |
| `milestone/m2-semantic-dom` | M2 | Semantic/Accessible DOM, stable IDs | 2 | `semantic/`, `accessibility/` |
| `milestone/m3-diffs-events` | M3 | Incremental diffs & event streaming | 2 | `events/` |
| `milestone/m4-vision-ocr` | M4 | Vision/OCR integration | 3 | `vision/` |
| `milestone/m5-network` | M5 | Network/API introspection | 2 | `network/` |
| `milestone/m6-accessibility` | M6 | Accessibility merging & queries | 1 | `accessibility/` polish |
| `milestone/m7-memory-planner` | M7 | Planner, Memory & Context | 2 | `memory/`, `planning/` |
| `milestone/m8-antibot` | M8 | Anti-bot / humanized input | 1 | `antibot/` |
| `milestone/m9-multiagent` | M9 | Multi-agent & orchestration | 1 | `multiagent/` |
| `milestone/m10-polish` | M10 | Testing, docs, optimization | 1 | `tests/`, `docs/` |

## Acceptance sketches

### M1 — Foundation
- [x] `Browser` starts Playwright and creates pages
- [x] `page.open`, `click`, `type`/`fill`, `snapshot`
- [x] CLI `agent-browser open <url>`
- [x] Basic tests without network flakiness where possible

### M2 — Semantic model
- [x] Role/name extraction + stable IDs across updates
- [x] `snapshot()` JSON matches design schema
- [x] Layout noise filtered from tree

### M3 — Diffs & events
- [x] `Diff` between snapshots
- [x] Event bus: navigation, element_added/removed, etc.
- [x] Optional MutationObserver path

### M4 — Vision
- [ ] Local OCR on screenshot regions
- [ ] `get_text_in_screenshot` API
- [ ] Optional UI detection hooks

### M5 — Network
- [ ] Request log + filter
- [ ] `wait_for_api`
- [ ] GraphQL detection basics

### M6 — Accessibility polish
- [ ] `get_by_role` / `get_by_label` style finders
- [ ] Robust AX merge

### M7 — Memory & planner
- [ ] Session KV + action history
- [ ] `context(max_tokens=...)`
- [ ] Rule-based `plan(goal)`

### M8 — Anti-bot
- [ ] Humanized delays / paths
- [ ] Document ethical use limits

### M9 — Multi-agent
- [ ] Attach multiple agents to session
- [ ] Event subscription per agent

### M10 — Polish
- [ ] Full test suite + docs
- [ ] Performance pass
- [ ] Security review notes
