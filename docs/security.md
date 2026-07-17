# Security review notes (M10)

Scope: library-level agent browser (Python + Playwright). Not a multi-tenant SaaS.

## Trust boundaries

| Boundary | Notes |
|----------|--------|
| Agent → Python API | Treat agent/LLM output as untrusted input; prefer element ids over raw selectors when possible |
| Python → Playwright | Local IPC; keep browser contexts isolated per `Browser` session |
| Page JS | Untrusted web content; sandbox is Chromium's; never `eval` agent strings without review |
| Memory store | May hold credentials; sensitive keys masked in summaries; optional SQLite at rest is plaintext unless OS encryption |

## Controls implemented

1. **Session isolation** — Each `Browser` uses its own Playwright context.
2. **Secret masking** — `MemoryStore` redacts password/token-like keys in logs/summaries.
3. **OCR privacy** — Local Tesseract preferred; no default cloud OCR.
4. **Humanize ethics** — Documented limits; not a CAPTCHA bypass tool (`docs/m8-antibot.md`).
5. **robots.txt flag** — `BrowserConfig.respect_robots_txt` (policy hook for callers).
6. **Typed errors** — Fail closed with clear exceptions rather than silent wrong targets.

## Recommendations for deployers

- Run headless agents in locked-down VMs/containers; limit egress.
- Do not log full `snapshot(include_raw_html=True)` in multi-tenant logs.
- Encrypt SQLite memory paths if persisting PII.
- Rotate credentials stored via `memory.set`.
- Keep Playwright/browser builds updated for Chromium CVEs.
- Legal review before large-scale automation; honor site ToS where required.

## Out of scope / residual risk

- Full anti-fingerprint vs modern bot defenses (arms race).
- XSS in pages affecting agent decisions (content trust).
- Supply-chain risk of third-party wheels (pin versions in production).
- M5 network capture (when implemented) will hold auth headers — encrypt & scope carefully.
