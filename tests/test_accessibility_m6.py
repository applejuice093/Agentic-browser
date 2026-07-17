"""M6 accessibility queries and get_by_* finders."""

from __future__ import annotations

import pytest

from agent_browser import Browser
from agent_browser.accessibility.queries import filter_by_label, filter_by_role
from agent_browser.models.element import Element

HTML = """
<!DOCTYPE html>
<html><head><title>A11y</title></head>
<body>
  <h1>Checkout</h1>
  <form>
    <label for="email">Email Address</label>
    <input id="email" name="email" type="email" placeholder="you@example.com"
           data-testid="email-field" />
    <label>
      Remember me
      <input id="remember" type="checkbox" name="remember" />
    </label>
    <button type="button" aria-label="Place order">Submit</button>
    <a href="#help">Need help?</a>
  </form>
</body></html>
"""


def test_filter_by_role_unit():
    els = [
        Element(id=1, role="button", text="Go", name="Go", visible=True),
        Element(id=2, role="link", text="Home", visible=True),
        Element(id=3, role="button", text="Cancel", visible=False),
    ]
    assert len(filter_by_role(els, "button")) == 1
    assert filter_by_role(els, "button", name="Go")[0].id == 1


def test_filter_by_label_unit():
    els = [
        Element(id=1, role="label", type="label", text="Email", attributes={"for": "e"}),
        Element(id=2, role="textbox", type="input", attributes={"id": "e"}, visible=True),
        Element(id=3, role="textbox", type="input", name="Phone", visible=True),
    ]
    found = filter_by_label(els, "Email")
    assert any(e.id == 2 for e in found)
    assert filter_by_label(els, "Phone")[0].id == 3


@pytest.mark.asyncio
async def test_get_by_role_and_label():
    async with Browser(headless=True) as browser:
        page = await browser.set_content(HTML)
        btn = await page.get_by_role("button", name="Place order")
        assert btn is not None
        assert btn.type == "button"

        email = await page.get_by_label("Email")
        assert email is not None
        await page.fill(email.id, "a@b.c")
        assert await page.get_value("#email") == "a@b.c"

        link = await page.get_by_role("link", name="help")
        assert link is not None

        heading = await page.get_by_role("heading", name="Checkout")
        assert heading is not None


@pytest.mark.asyncio
async def test_get_by_placeholder_text_testid():
    async with Browser(headless=True) as browser:
        page = await browser.set_content(HTML)
        ph = await page.get_by_placeholder("you@")
        assert ph is not None
        txt = await page.get_by_text("Need help")
        assert txt is not None
        tid = await page.get_by_test_id("email-field")
        assert tid is not None
        assert tid.attributes.get("id") == "email"
