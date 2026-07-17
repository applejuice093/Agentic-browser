"""M7 memory, context, and planner tests."""

from __future__ import annotations

import pytest

from agent_browser import Browser
from agent_browser.memory import MemoryStore
from agent_browser.models.element import Element
from agent_browser.models.snapshot import Snapshot
from agent_browser.planning import ContextBuilder, Planner


def test_memory_kv_and_mask():
    mem = MemoryStore("s1")
    mem.set("email", "a@b.c")
    mem.set("password", "supersecret")
    assert mem.get("email") == "a@b.c"
    summary = mem.memory_summary()
    assert summary["kv"]["password"] == "***"
    assert summary["kv"]["email"] == "a@b.c"
    mem.log_action({"type": "fill", "field": "password", "value": "x"})
    assert mem.actions()[-1]["value"] == "***"


def test_planner_suggests_login():
    snap = Snapshot(
        url="https://x/login",
        title="Login",
        elements=[
            Element(id=1, role="textbox", name="Email", visible=True, enabled=True),
            Element(id=2, role="textbox", name="Password", visible=True, enabled=True),
            Element(id=3, role="button", text="Sign in", visible=True, enabled=True),
        ],
    )
    plan = Planner().plan(snap, "login to my account")
    assert any("Goal" in s for s in plan)
    actions = Planner().suggest_actions(snap, "login")
    assert any(a["element_id"] == 3 for a in actions)


def test_context_token_budget():
    els = [
        Element(id=i, role="button", text=f"B{i}", visible=True, enabled=True)
        for i in range(1, 40)
    ]
    snap = Snapshot(url="https://x", title="T", elements=els)
    ctx = ContextBuilder().build(snap, max_tokens=100)
    assert ctx["element_included"] < 40
    assert ctx["approx_tokens"] <= 120


@pytest.mark.asyncio
async def test_page_context_and_plan():
    html = """
    <html><head><title>Shop</title></head>
    <body>
      <input id="q" placeholder="Search" />
      <button id="go">Search</button>
      <button id="cart">Checkout</button>
    </body></html>
    """
    async with Browser(headless=True) as browser:
        page = await browser.set_content(html)
        await page.fill("#q", "shoes")
        ctx = await page.context(max_tokens=500, goal="search products")
        assert ctx["title"] == "Shop"
        assert ctx["current_goal"] == "search products"
        plan = await page.plan("search for shoes")
        assert isinstance(plan, list)
        assert browser.memory.get("current_goal") == "search for shoes"
        assert len(page.memory.actions()) >= 1
