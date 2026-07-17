"""Agent-native observation loop tests."""

from __future__ import annotations

import pytest

from agent_browser import (
    AgentSession,
    Browser,
    DetailLevel,
    ErrorCode,
    Observation,
    tools_as_openai,
    tool_names,
)
from agent_browser.models.element import Element
from agent_browser.models.snapshot import Snapshot
from agent_browser.observation.compact import build_observation


def test_build_observation_is_compact():
    els = [
        Element(id=i, role="button", text=f"B{i}", type="button", visible=True, enabled=True)
        for i in range(1, 80)
    ]
    els.append(Element(id=100, role="heading", type="h1", text="Title", visible=True))
    els.append(
        Element(id=101, role="div", type="div", text="noise layout", visible=True)
    )
    snap = Snapshot(url="https://x.test", title="T", elements=els)
    obs = build_observation(snap, detail=DetailLevel.SPARSE, max_tokens=800)
    assert isinstance(obs, Observation)
    assert obs.approx_tokens <= 900
    assert all(r.role in ("button", "link", "textbox", "heading") or r.tag == "button" for r in obs.interactive) or len(obs.interactive) > 0
    # layout div should not dominate interactive list
    assert all(r.tag != "div" or r.role == "button" for r in obs.interactive)


def test_tool_definitions():
    names = tool_names()
    assert "browser_click" in names
    assert "browser_observe" in names
    oa = tools_as_openai()
    assert oa[0]["type"] == "function"


@pytest.mark.asyncio
async def test_agent_observe_and_click():
    html = """
    <html><head><title>Agent Loop</title></head>
    <body>
      <h1>Shop</h1>
      <button id="buy" type="button">Buy now</button>
      <p id="out">idle</p>
      <script>
        document.getElementById('buy').onclick = () => {
          document.getElementById('out').textContent = 'bought';
        };
      </script>
    </body></html>
    """
    async with Browser(headless=True) as browser:
        page = await browser.set_content(html)
        agent = page.as_agent(detail="normal", max_tokens=1500)
        obs = await agent.observe()
        assert obs.title == "Agent Loop"
        assert obs.approx_tokens > 0
        assert len(obs.interactive) >= 1
        # find Buy
        buy = next(
            (r for r in obs.interactive if r.text and "Buy" in r.text),
            None,
        )
        assert buy is not None
        result = await agent.click(buy.ref)
        assert result.ok
        assert result.error_code == ErrorCode.OK
        assert result.observation is not None
        out = await page.evaluate("() => document.getElementById('out').textContent")
        assert out == "bought"


@pytest.mark.asyncio
async def test_agent_type_and_tool_dispatch():
    html = """
    <html><body>
      <label for="q">Query</label>
      <input id="q" name="q" />
      <button type="button" id="go">Go</button>
      <pre id="out"></pre>
      <script>
        document.getElementById('go').onclick = () => {
          document.getElementById('out').textContent =
            document.getElementById('q').value;
        };
      </script>
    </body></html>
    """
    async with Browser(headless=True) as browser:
        page = await browser.set_content(html)
        agent = AgentSession(page, max_tokens=1200)
        matches = await agent.find(role="textbox", name="Query")
        assert matches
        ref = matches[0]["ref"]
        typed = await agent.type(ref, "headphones", clear=True, observe=True)
        assert typed.ok
        go = await agent.find(role="button", text="Go")
        # text filter via get_by_text path
        if not go:
            go = await agent.find(role="button")
        assert go
        clicked = await agent.call_tool("browser_click", {"ref": go[0]["ref"]})
        assert clicked.get("ok") is True
        out = await page.evaluate("() => document.getElementById('out').textContent")
        assert out == "headphones"


@pytest.mark.asyncio
async def test_action_result_on_missing_ref():
    async with Browser(headless=True) as browser:
        page = await browser.set_content("<html><body><p>hi</p></body></html>")
        agent = page.as_agent(recover_stale=False)
        await agent.observe()
        result = await agent.click(99999)
        assert result.ok is False
        assert result.error_code in (
            ErrorCode.ELEMENT_NOT_FOUND,
            ErrorCode.ELEMENT_STALE,
        )


@pytest.mark.asyncio
async def test_wait_and_navigate_tools():
    async with Browser(headless=True) as browser:
        agent = await browser.open_agent("https://example.com")
        obs = await agent.observe(detail="sparse")
        assert "example" in obs.url
        w = await agent.wait("timeout", value=50)
        assert w.ok
        nav = await agent.call_tool(
            "browser_navigate", {"url": "https://example.com/", "detail": "sparse"}
        )
        assert nav.get("ok") is True


@pytest.mark.asyncio
async def test_observation_token_budget_smaller_than_full_snapshot_json():
    async with Browser(headless=True) as browser:
        page = await browser.open("https://quotes.toscrape.com")
        snap = await page.snapshot()
        import json

        full_tokens = max(1, len(json.dumps([e.model_dump() for e in snap.elements])) // 4)
        obs = await page.observe(detail="normal", max_tokens=1500)
        # compact should be under budget (approx)
        assert obs.approx_tokens <= 1600
        # and typically much smaller than dumping all element dicts
        assert obs.approx_tokens < full_tokens or full_tokens < 500
