# M7 — Memory, planner & context

**Branch:** `milestone/m7-memory-planner`

## Acceptance

| Item | Status |
|------|--------|
| Session KV + action history | Done |
| `context(max_tokens=...)` | Done |
| Rule-based `plan(goal)` | Done |

## API

```python
await page.fill("#email", "a@b.c")
ctx = await page.context(max_tokens=1000, goal="complete checkout")
plan = await page.plan("complete checkout")
print(page.memory_summary())
browser.memory.set("shipping_address", "123 Main")
```

Sensitive keys (`password`, `token`, …) are masked in summaries/logs.
Optional SQLite: `MemoryStore(session_id, db_path="data/memory.db")`.
