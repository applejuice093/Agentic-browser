"""M2 integration tests: semantic snapshot, stable IDs, find() — offline HTML."""

from __future__ import annotations

import pytest

from agent_browser import Browser

SEMANTIC_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>Semantic Fixture</title></head>
<body>
  <header>
    <nav aria-label="Main">
      <a href="#home">Home</a>
      <a href="#about">About</a>
    </nav>
  </header>
  <main>
    <h1>Products</h1>
    <div class="layout-wrapper">
      <div class="spacer"></div>
      <form id="search-form" role="search">
        <label for="q">Query</label>
        <input id="q" name="q" type="search" placeholder="Search products" />
        <button id="search-btn" type="button">Search</button>
      </form>
      <ul id="results">
        <li><button type="button" class="item">Alpha</button></li>
        <li><button type="button" class="item">Beta</button></li>
      </ul>
      <p id="status">idle</p>
    </div>
  </main>
  <script>
    document.getElementById('search-btn').onclick = function () {
      document.getElementById('status').textContent =
        'q=' + document.getElementById('q').value;
    };
    document.querySelectorAll('.item').forEach(function (btn) {
      btn.onclick = function () {
        document.getElementById('status').textContent = 'item=' + btn.textContent;
      };
    });
  </script>
</body>
</html>
"""


@pytest.fixture
async def page():
    async with Browser(headless=True) as browser:
        p = await browser.set_content(SEMANTIC_HTML)
        yield p


@pytest.mark.asyncio
async def test_semantic_snapshot_schema(page):
    snap = await page.snapshot()
    assert snap.title == "Semantic Fixture"
    assert len(snap.elements) >= 5

    for el in snap.elements:
        assert isinstance(el.id, int) and el.id >= 1
        assert el.role is not None
        assert el.type is not None
        # design schema fields present
        assert hasattr(el, "parent_id")
        assert hasattr(el, "children_ids")
        assert hasattr(el, "visible")
        assert hasattr(el, "enabled")

    # Interactive stamped
    stamped = await page.evaluate(
        "() => document.querySelectorAll('[data-agent-id]').length"
    )
    assert stamped == len(snap.elements)


@pytest.mark.asyncio
async def test_roles_and_headings(page):
    snap = await page.snapshot()
    roles = {e.role for e in snap.elements}
    assert "heading" in roles or any(e.type == "h1" for e in snap.elements)
    assert "button" in roles or any(e.type == "button" for e in snap.elements)
    assert "link" in roles or any(e.type == "a" for e in snap.elements)

    h1 = next((e for e in snap.elements if e.type == "h1" or e.role == "heading"), None)
    assert h1 is not None
    assert "Products" in (h1.text or "")


@pytest.mark.asyncio
async def test_layout_noise_filtered(page):
    snap = await page.snapshot()
    # Pure spacer divs without semantics should not dominate the model
    empty_divs = [
        e
        for e in snap.elements
        if e.type == "div" and not (e.text or "").strip() and not e.name and e.role in ("div", None)
    ]
    assert len(empty_divs) <= 1


@pytest.mark.asyncio
async def test_parent_child_links(page):
    snap = await page.snapshot()
    form = next((e for e in snap.elements if e.attributes.get("id") == "search-form"), None)
    assert form is not None
    # Form should have children (input and/or button)
    assert len(form.children_ids) >= 1
    for cid in form.children_ids:
        child = next(e for e in snap.elements if e.id == cid)
        assert child.parent_id == form.id


@pytest.mark.asyncio
async def test_stable_ids_across_mutations(page):
    snap1 = await page.snapshot()
    btn = next(e for e in snap1.elements if e.attributes.get("id") == "search-btn")
    email = next(e for e in snap1.elements if e.attributes.get("id") == "q")
    btn_id, q_id = btn.id, email.id

    await page.fill(q_id, "headphones")
    await page.click(btn_id)

    snap2 = await page.snapshot()
    btn2 = next(e for e in snap2.elements if e.attributes.get("id") == "search-btn")
    q2 = next(e for e in snap2.elements if e.attributes.get("id") == "q")
    assert btn2.id == btn_id
    assert q2.id == q_id

    status = await page.evaluate("() => document.getElementById('status').textContent")
    assert status == "q=headphones"


@pytest.mark.asyncio
async def test_find_by_role_and_text(page):
    el = await page.find(role="button", text_contains="Search")
    assert el is not None
    assert el.type == "button"

    items = await page.find_all(role="button", text_contains="Alpha")
    assert len(items) >= 1
    await page.click(items[0].id)
    status = await page.evaluate("() => document.getElementById('status').textContent")
    assert status == "item=Alpha"


@pytest.mark.asyncio
async def test_find_by_name(page):
    # label "Query" associated with input
    el = await page.find(name="Query")
    assert el is not None
    assert el.type in ("input", "label") or el.role in ("textbox", "searchbox", "label")


@pytest.mark.asyncio
async def test_ids_reset_on_navigation(page):
    snap1 = await page.snapshot()
    assert snap1.elements
    first_ids = {e.attributes.get("id"): e.id for e in snap1.elements if e.attributes.get("id")}

    await page.set_content(
        "<html><head><title>Other</title></head>"
        "<body><button id='search-btn'>X</button></body></html>"
    )
    snap2 = await page.snapshot()
    # New document — assigner reset, ids start fresh; button may be id 1
    assert snap2.title == "Other"
    assert all(e.id >= 1 for e in snap2.elements)
    # Counter was reset so small ids reappear
    assert min(e.id for e in snap2.elements) == 1


@pytest.mark.asyncio
async def test_click_find_result(page):
    beta = await page.find(role="button", text_contains="Beta")
    assert beta is not None
    await page.click(beta)
    status = await page.evaluate("() => document.getElementById('status').textContent")
    assert status == "item=Beta"
