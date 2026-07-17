"""Async event streaming bus (M3)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

from agent_browser.models.events import BrowserEvent


class EventBus:
    """Publish/subscribe for page events. Full implementation in M3."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[BrowserEvent], Any]] = []
        self._queue: asyncio.Queue[BrowserEvent] = asyncio.Queue()

    def subscribe(self, handler: Callable[[BrowserEvent], Any]) -> None:
        self._subscribers.append(handler)

    async def emit(self, event: BrowserEvent) -> None:
        await self._queue.put(event)
        for handler in self._subscribers:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result

    async def stream(self) -> AsyncIterator[BrowserEvent]:
        while True:
            yield await self._queue.get()
