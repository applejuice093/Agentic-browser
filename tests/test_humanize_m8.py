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


def test_rejects_inverted_ranges():
    with pytest.raises(ValueError):
        HumanizedInput(min_delay_ms=200, max_delay_ms=50)
    with pytest.raises(ValueError):
        HumanizedInput(click_pause_ms=(300, 100))
    with pytest.raises(ValueError):
        HumanizedInput(move_steps=(30, 5))


def test_target_point_stays_inside_tiny_boxes():
    h = HumanizedInput()
    # A 1x1 box used to be clamped to x + 1, i.e. just outside the element.
    p = h.target_point_from_box(100, 200, 1, 1)
    assert (p.x, p.y) == (100.5, 200.5)
    for _ in range(200):
        q = h.target_point_from_box(10, 20, 40, 6)
        assert 11 <= q.x <= 49 and 21 <= q.y <= 25
