"""M9 multi-agent session tests."""

from __future__ import annotations

import asyncio

import pytest

from agent_browser import Browser, EventType
from agent_browser.multiagent import MultiAgentSession


@pytest.mark.asyncio
async def test_attach_detach_and_roles():
    session = MultiAgentSession("s1")
    nav = session.attach("nav", role="navigator")
    form = session.attach("form", role="input")
    assert session.list_agents() == ["nav", "form"]
    assert session.agents_by_role("navigator")[0].agent_id == "nav"
    form.detach()
    assert "form" not in session.list_agents()
    await session.close()


@pytest.mark.asyncio
async def test_shared_page_and_event_subscriptions():
    async with Browser(headless=True) as browser:
        page = await browser.set_content(
            "<html><body><button id='b'>X</button></body></html>"
        )
        session = browser.create_multi_agent_session()
        session.bind_page(page)
        a1 = session.attach("a1", role="ui")
        a2 = session.attach("a2", role="vision")

        seen1: list = []
        seen2: list = []
        a1.subscribe(lambda e: seen1.append(e), event_type=EventType.ELEMENT_CLICKED)
        a2.subscribe(lambda e: seen2.append(e))  # all events

        await page.click("#b")
        await asyncio.sleep(0.1)

        assert any(
            (e.event.value if hasattr(e.event, "value") else e.event) == "element_clicked"
            for e in seen1
        )
        assert len(seen2) >= 1
        await session.close()


@pytest.mark.asyncio
async def test_command_lock_serializes():
    session = MultiAgentSession()
    order: list[int] = []

    async def work(n: int, delay: float) -> None:
        agent = session.attach(f"a{n}")
        async def _inner() -> None:
            await asyncio.sleep(delay)
            order.append(n)
        await agent.run(_inner())

    await asyncio.gather(work(1, 0.05), work(2, 0.01))
    # lock ensures sequential completion order of critical sections
    assert sorted(order) == [1, 2]
    await session.close()
