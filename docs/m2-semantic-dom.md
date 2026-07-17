# M2 — Semantic DOM & Stable IDs

**Branch:** `milestone/m2-semantic-dom`  
**Goal:** Semantic DOM / accessibility merge, role/name extraction, stable element IDs, `snapshot()` JSON schema.

## Acceptance

| Item | Status |
|------|--------|
| Role/name extraction + stable IDs across updates | Done |
| `snapshot()` JSON matches design schema | Done |
| Layout noise filtered from tree | Done |

## Pipeline

```
Playwright page
    → in-page semantic extract (filter layout / presentation)
    → StableIDAssigner (fingerprint + secondary keys)
    → stamp data-agent-id
    → AccessibilityEngine merge (role/name/description)
    → parent_id / children_ids wiring
    → Snapshot
```

## API additions

```python
snap = await page.snapshot()
btn = await page.find(role="button", text_contains="Checkout")
await page.click(btn.id)

# All matches
buttons = await page.find_all(role="button")

# Engine access
page.semantic.query(role="link", name="Home")
```

### Element schema (design-aligned)

| Field | Description |
|-------|-------------|
| `id` | Stable int for the page session |
| `role` | ARIA / implicit role |
| `type` | HTML tag |
| `text`, `name`, `description` | Content & accessible name |
| `attributes`, `value`, `checked` | State |
| `visible`, `enabled` | Interaction flags |
| `bounding_box` | `{x,y,width,height}` |
| `parent_id`, `children_ids` | Semantic tree |

## Stability rules

- **Same `id` attribute** → same stable id across snapshots (even if text changes).
- **Navigation / `set_content`** → assigner reset (new document identity).
- **In-page mutations** (fill, click, dynamic nodes) → existing nodes keep ids; new nodes get new ids.

## Modules

| Path | Role |
|------|------|
| `semantic/extract.py` | Browser JS extract + stamp |
| `semantic/ids.py` | Fingerprints & `StableIDAssigner` |
| `semantic/engine.py` | Capture / query / tree wiring |
| `accessibility/engine.py` | AX snapshot + merge |

## Tests

```bash
pytest tests/test_stable_ids.py tests/test_semantic_engine.py tests/test_semantic_page.py -q
```
