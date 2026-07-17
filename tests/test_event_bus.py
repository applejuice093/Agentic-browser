"""Unit tests for EventBus (M3)."""

import asyncio

import pytest

from agent_browser.events.bus import EventBus
from agent_browser.models.events import BrowserEvent, EventType


@pytest.mark.asyncio
async def test_subscribe_and_emit():
    bus = EventBus()
    seen: list[BrowserEvent] = []
    bus.subscribe(lambda e: seen.append(e))
    await bus.emit(BrowserEvent.make(EventType.ELEMENT_CLICKED, id=1))
    assert len(seen) == 1
    assert seen[0].data["id"] == 1


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    seen: list = []
    unsub = bus.subscribe(lambda e: seen.append(e))
    unsub()
    await bus.emit(BrowserEvent.make(EventType.NAVIGATION, to_url="x"))
    assert seen == []


@pytest.mark.asyncio
async def test_history():
    bus = EventBus(history_size=10)
    await bus.emit(BrowserEvent.make(EventType.MUTATION, childList=1))
    await bus.emit(BrowserEvent.make(EventType.PAGE_CHANGED, summary={}))
    assert len(bus.history()) == 2
    assert len(bus.history(event_type=EventType.MUTATION)) == 1


@pytest.mark.asyncio
async def test_wait_for():
    bus = EventBus()

    async def later() -> None:
        await asyncio.sleep(0.05)
        await bus.emit(BrowserEvent.make(EventType.ELEMENT_ADDED, id=9))

    task = asyncio.create_task(later())
    ev = await bus.wait_for(EventType.ELEMENT_ADDED, timeout=2.0)
    await task
    assert ev.data["id"] == 9


@pytest.mark.asyncio
async def test_stream():
    bus = EventBus()

    async def producer() -> None:
        await asyncio.sleep(0.02)
        await bus.emit(BrowserEvent.make(EventType.TEXT_CHANGED, id=1, text="x"))
        await bus.close()

    task = asyncio.create_task(producer())
    received = []
    async for event in bus.stream():
        received.append(event)
    await task
    assert len(received) == 1
