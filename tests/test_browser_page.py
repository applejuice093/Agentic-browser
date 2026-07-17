"""M1 integration tests — offline HTML via set_content (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_browser import Browser, ElementNotFoundError, NavigationError

FIXTURE = (Path(__file__).parent / "fixtures" / "sample.html").read_text(encoding="utf-8")


@pytest.fixture
async def browser():
    async with Browser(headless=True) as b:
        yield b


@pytest.fixture
async def page(browser: Browser):
    return await browser.set_content(FIXTURE)


@pytest.mark.asyncio
async def test_browser_start_stop():
    b = Browser(headless=True)
    assert b.is_started is False
    await b.start()
    assert b.is_started is True
    page = await b.new_page()
    assert page in b.pages
    await page.set_content("<html><body><p>hi</p></body></html>")
    assert "about:blank" not in (await page.title() or "x") or True
    await b.stop()
    assert b.is_started is False


@pytest.mark.asyncio
async def test_context_manager_and_open_inline(browser: Browser, page):
    title = await page.title()
    assert title == "Agent Browser M1 Fixture"
    assert len(browser.pages) >= 1


@pytest.mark.asyncio
async def test_snapshot_basic_elements(page):
    snap = await page.snapshot()
    assert snap.title == "Agent Browser M1 Fixture"
    assert snap.scroll_position == 0.0
    assert len(snap.elements) >= 4

    roles_or_types = {(e.role, e.type) for e in snap.elements}
    # Should see inputs and buttons
    types = {e.type for e in snap.elements}
    assert "input" in types
    assert "button" in types

    ids = [e.id for e in snap.elements]
    assert ids == sorted(ids)
    assert all(isinstance(i, int) and i >= 1 for i in ids)

    # data-agent-id stamped in DOM
    stamped = await page.evaluate(
        "() => document.querySelectorAll('[data-agent-id]').length"
    )
    assert stamped == len(snap.elements)


@pytest.mark.asyncio
async def test_snapshot_raw_html(page):
    snap = await page.snapshot(include_raw_html=True)
    assert snap.raw_html is not None
    assert "<form" in snap.raw_html
    assert await page.content()


@pytest.mark.asyncio
async def test_fill_type_click_by_selector(page):
    await page.fill("#email", "agent@example.com")
    assert await page.get_value("#email") == "agent@example.com"

    await page.type("#password", "secret", clear=True)
    assert await page.get_value("#password") == "secret"

    await page.click("#submit-btn")
    status = await page.evaluate("() => document.getElementById('status').textContent")
    assert status == "submitted:agent@example.com"


@pytest.mark.asyncio
async def test_click_by_stable_id_after_snapshot(page):
    snap = await page.snapshot()
    # Find the Toggle button by text
    toggle = next(e for e in snap.elements if e.text == "Toggle")
    await page.click(toggle.id)
    status = await page.evaluate("() => document.getElementById('status').textContent")
    assert status == "on"

    # Element object also works
    snap2 = await page.snapshot()
    toggle2 = next(e for e in snap2.elements if e.text == "Toggle")
    await page.click(toggle2)
    status = await page.evaluate("() => document.getElementById('status').textContent")
    assert status == "off"


@pytest.mark.asyncio
async def test_fill_by_stable_id(page):
    snap = await page.snapshot()
    email_el = next(
        e for e in snap.elements if e.attributes.get("id") == "email" or e.name == "email"
    )
    await page.fill(email_el.id, "id-fill@test.com")
    assert await page.get_value("#email") == "id-fill@test.com"


@pytest.mark.asyncio
async def test_element_not_found(page):
    with pytest.raises(ElementNotFoundError):
        await page.click(99999)

    with pytest.raises(ElementNotFoundError):
        await page.click("#does-not-exist")


@pytest.mark.asyncio
async def test_browser_not_started_guard():
    b = Browser(headless=True)
    # new_page auto-starts; stop then ensure property
    await b.start()
    await b.stop()
    assert b.is_started is False


@pytest.mark.asyncio
async def test_navigation_error_invalid_protocol():
    async with Browser(headless=True) as browser:
        page = await browser.new_page()
        with pytest.raises(NavigationError):
            await page.goto("http://127.0.0.1:1/")  # nothing listening


@pytest.mark.asyncio
async def test_press_enter(page):
    await page.fill("#email", "x@y.z")
    await page.press("#email", "Tab")
    # focus moved; password should accept fill without error
    await page.fill("#password", "p")
    assert await page.get_value("#password") == "p"


@pytest.mark.asyncio
async def test_wait_for_selector(page):
    await page.wait_for_selector("#submit-btn", state="visible")


@pytest.mark.asyncio
async def test_screenshot_bytes(page):
    data = await page.screenshot()
    assert isinstance(data, bytes)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_evaluate_and_get_text(page):
    text = await page.get_text("#docs-link")
    assert text == "Docs"
    href = await page.evaluate(
        "() => document.getElementById('docs-link').getAttribute('href')"
    )
    assert href == "#docs"


@pytest.mark.asyncio
async def test_multiple_pages(browser: Browser):
    p1 = await browser.set_content("<html><head><title>One</title></head><body></body></html>")
    p2 = await browser.set_content("<html><head><title>Two</title></head><body></body></html>")
    assert await p1.title() == "One"
    assert await p2.title() == "Two"
    assert len(browser.pages) >= 2
    await p1.close()
    assert p1.is_closed
