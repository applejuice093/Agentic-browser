"""M8 humanized input tests."""

from __future__ import annotations

import pytest

from agent_browser import Browser
from agent_browser.antibot import HumanizedInput, Point


def test_mouse_path_curved():
    h = HumanizedInput(enabled=True)
    path = h.mouse_path(Point(0, 0), Point(100, 100), steps=12)
    assert len(path) == 12
    assert path[-1].x == pytest.approx(100, abs=3)
    assert path[-1].y == pytest.approx(100, abs=3)


def test_disabled_instant():
    h = HumanizedInput(enabled=False)
    assert h.keystroke_delay_ms() == 0
    path = h.mouse_path((0, 0), (50, 50))
    assert len(path) == 1


def test_typing_profile_length():
    h = HumanizedInput(enabled=True)
    delays = h.typing_profile("hi there")
    assert len(delays) == len("hi there")
    assert all(d > 0 for d in delays)


@pytest.mark.asyncio
async def test_humanized_click():
    async with Browser(headless=True) as browser:
        page = await browser.set_content(
            "<html><body><button id='b'>Go</button>"
            "<script>document.getElementById('b').onclick=()=>{"
            "document.body.dataset.clicked='1'};</script></body></html>"
        )
        page.set_humanize(True)
        await page.click("#b")
        assert await page.evaluate("() => document.body.dataset.clicked") == "1"
