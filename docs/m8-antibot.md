# M8 — Anti-bot / humanized input

**Branch:** `milestone/m8-antibot`

## Acceptance

| Item | Status |
|------|--------|
| Humanized delays / paths | Done |
| Document ethical use limits | Done (this doc) |

## API

```python
async with Browser(humanize=True) as browser:  # via config
    ...

page.set_humanize(True)
await page.click("#buy")          # curved mouse path + delay
await page.type("#q", "hello")    # per-keystroke delays
```

Config env: `AGENT_BROWSER_HUMANIZE=true`.

## Ethical use

- Use only on **sessions you own / are authorized** to automate.
- Humanization reduces *robotic timing fingerprints*; it is **not** a CAPTCHA solver
  and must not be used to violate site terms, robots.txt policy, or the law.
- Prefer rate limits, user consent, and compliance checks (see design threat model).
- Do not use this to harass, spam, or access accounts without permission.
