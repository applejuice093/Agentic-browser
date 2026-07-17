# M10 — Polish, testing, optimization, security

**Branch:** `milestone/m10-polish`

## Acceptance

| Item | Status |
|------|--------|
| Full test suite + docs | Done |
| Performance pass | Done (notes below) |
| Security review notes | Done |

## Documentation index

| Doc | Milestone |
|-----|-----------|
| [m1-foundation.md](./m1-foundation.md) | Core Playwright API |
| [m2-semantic-dom.md](./m2-semantic-dom.md) | Semantic DOM + stable IDs |
| [m3-diffs-events.md](./m3-diffs-events.md) | Diffs + events |
| [m4-vision-ocr.md](./m4-vision-ocr.md) | OCR / vision |
| [m6-accessibility.md](./m6-accessibility.md) | get_by_role / label |
| [m7-memory-planner.md](./m7-memory-planner.md) | Memory + plan/context |
| [m8-antibot.md](./m8-antibot.md) | Humanized input |
| [m9-multiagent.md](./m9-multiagent.md) | Multi-agent |
| [security.md](./security.md) | Security review |
| [architecture.md](./architecture.md) | Architecture map |
| [milestones.md](./milestones.md) | Roadmap checklist |

> **M5 (Network intelligence)** was deferred in this push sequence; scaffold remains under `src/agent_browser/network/`.

## Performance notes

1. **Snapshot cost** — Semantic extract runs in-page JS once per `snapshot()`. Prefer `find(..., refresh=False)` / `get_by_*` after a single snapshot when chaining queries.
2. **OCR** — Never automatic on navigation; call `get_text_in_screenshot` / `ocr` only when needed. Runs in a worker thread.
3. **Mutation watch** — Debounce ≥50–100ms; disable `auto_snapshot` if agents only need raw `mutation` events.
4. **Humanize** — Extra mouse steps add latency; keep off for pure automation benchmarks.
5. **Context builder** — `max_tokens` caps element inclusion (approx 4 chars/token).

## Test matrix

```bash
pip install -e ".[dev]"
playwright install chromium
pytest -q
```

Optional vision:

```bash
pip install -e ".[vision]"
# system tesseract for live OCR tests (mocked in CI)
```

## Release checklist

- [x] Milestone acceptance boxes updated
- [x] Public exports in `agent_browser.__init__`
- [x] CLI `version` / `open`
- [x] Security notes published
- [x] Merge into `dev` + `master`
