# M6 — Accessibility polish

**Branch:** `milestone/m6-accessibility`

## Acceptance

| Item | Status |
|------|--------|
| `get_by_role` / `get_by_label` style finders | Done |
| Robust AX merge | Done (scored matching) |

## API

```python
btn = await page.get_by_role("button", name="Place order")
email = await page.get_by_label("Email")
await page.fill(email.id, "user@example.com")
await page.click(btn.id)

await page.get_by_placeholder("Search")
await page.get_by_text("Checkout")
await page.get_by_test_id("email-field")
```

Also: `get_all_by_role`, `get_all_by_label`.
