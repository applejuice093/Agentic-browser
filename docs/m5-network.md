# M5 — Network / API intelligence

**Branch:** `milestone/m5-network`

## Acceptance

| Item | Status |
|------|--------|
| Request log + filter | Done |
| `wait_for_api` | Done |
| GraphQL detection basics | Done |

## API

```python
await page.route("**/api/cart**", fulfill_json={"ok": True})  # optional mock
await page.click("#checkout")
req = await page.wait_for_api("/api/cart", timeout_ms=15_000)
print(req.response_status, req.response_body)

calls = page.network_requests(filter="api")
gql = page.list_network_requests(graphql_only=True)
page.clear_network_log()
```

## Features

- Captures XHR/fetch (and API-like URLs) with method, status, headers, bodies
- Sensitive headers (`Authorization`, `Cookie`, …) masked as `***`
- GraphQL POST detection + operation name extraction
- `wait_for_api(pattern)` — substring, glob, or `re:` regex
- Emits `api_call` / `network_error` on the page event bus
- `route()` helper for fulfilling JSON (tests / offline agents)

See full **[User Guide](./USER_GUIDE.md)**.
