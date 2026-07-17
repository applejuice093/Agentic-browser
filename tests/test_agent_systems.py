"""Tests for overlay dismiss, settle, noise filtering, recovery-oriented observe."""

from __future__ import annotations

import pytest

from agent_browser import Browser
from agent_browser.agent.overlays import is_noise_text
from agent_browser.models.element import Element
from agent_browser.models.observation import DetailLevel
from agent_browser.models.snapshot import Snapshot
from agent_browser.observation.compact import build_observation


def test_noise_text_detection():
    assert is_noise_text("Privacy Preference Center")
    assert is_noise_text("Manage Consent Preferences")
    assert is_noise_text("Cookie List")
    assert not is_noise_text("Ultimate Edition")
    assert not is_noise_text("Pre-Order Now")


def test_observation_filters_cookie_headings():
    els = [
        Element(id=1, role="heading", type="h2", text="Privacy Preference Center", visible=True),
        Element(id=2, role="heading", type="h4", text="Ultimate Edition", visible=True),
        Element(id=3, role="button", type="button", text="Accept All", visible=True, enabled=True),
        Element(id=4, role="button", type="button", text="Pre-Order Now", visible=True, enabled=True),
        Element(id=5, role="link", type="a", text="Trailer 2", visible=True, enabled=True,
                attributes={"href": "/trailer"}),
    ]
    snap = Snapshot(url="https://x/VI", title="GTA VI", elements=els)
    obs = build_observation(snap, detail=DetailLevel.NORMAL, max_tokens=1500)
    heading_texts = [h.text for h in obs.headings]
    assert "Privacy Preference Center" not in heading_texts
    assert any(h and "Ultimate" in h for h in heading_texts)
    assert obs.summary and "GTA" in obs.summary
    # Pre-order should rank in interactive
    texts = " ".join((r.text or "") for r in obs.interactive)
    assert "Pre-Order" in texts or "Trailer" in texts


@pytest.mark.asyncio
async def test_dismiss_cookie_banner_fixture():
    html = """
    <html><head><title>Shop</title></head>
    <body>
      <div id="onetrust-banner-sdk" role="dialog" aria-label="cookie">
        <p>We use cookies</p>
        <button id="onetrust-accept-btn-handler">Accept All</button>
      </div>
      <h1>Real Product</h1>
      <button id="buy">Buy</button>
      <script>
        document.getElementById('onetrust-accept-btn-handler').onclick = () => {
          document.getElementById('onetrust-banner-sdk').style.display = 'none';
          document.body.dataset.accepted = '1';
        };
      </script>
    </body></html>
    """
    async with Browser(headless=True) as browser:
        page = await browser.set_content(html)
        agent = page.as_agent(auto_settle=True)
        stats = await agent.dismiss_overlays()
        assert stats.get("clicked") or stats.get("hidden_nodes")
        # banner gone or hidden
        visible = await page.evaluate(
            """() => {
              const el = document.getElementById('onetrust-banner-sdk');
              if (!el) return false;
              const s = getComputedStyle(el);
              return s.display !== 'none' && s.visibility !== 'hidden';
            }"""
        )
        assert visible is False or (await page.evaluate("() => document.body.dataset.accepted")) == "1"
        obs = await agent.observe(prepare=False)
        assert any(r.text and "Buy" in r.text for r in obs.interactive)


@pytest.mark.asyncio
async def test_prepare_and_observe_summary():
    async with Browser(headless=True) as browser:
        page = await browser.set_content(
            "<html><head><title>Demo</title></head>"
            "<body><h1>Hello</h1><a href='#x'>Next</a></body></html>"
        )
        agent = page.as_agent()
        await agent.prepare(force=True)
        obs = await agent.observe(prepare=False)
        assert obs.title == "Demo"
        assert obs.summary
        assert obs.approx_tokens > 0
