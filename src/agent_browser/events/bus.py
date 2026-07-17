"""Async event streaming bus (M3)."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import Any

from agent_browser.models.events import BrowserEvent, EventType

EventHandler = Callable[[BrowserEvent], Any]


class EventBus:
    """
    Publish/subscribe + async stream for page events.

    - ``subscribe`` / ``unsubscribe`` for push handlers
    - ``stream()`` async iterator for agents that pull events
    - optional ring-buffer history for late subscribers
    """

    def __init__(self, *, history_size: int = 256) -> None:
        self._subscribers: list[EventHandler] = []
        self._queues: list[asyncio.Queue[BrowserEvent | None]] = []
        self._history: deque[BrowserEvent] = deque(maxlen=history_size)
        self._closed = False

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        """Register a handler; returns an unsubscribe callable."""
        self._subscribers.append(handler)

        def _unsub() -> None:
            try:
                self._subscribers.remove(handler)
            except ValueError:
                pass

        return _unsub

    def unsubscribe(self, handler: EventHandler) -> None:
        try:
            self._subscribers.remove(handler)
        except ValueError:
            pass

    async def emit(self, event: BrowserEvent) -> None:
        if self._closed:
            return
        self._history.append(event)
        for q in list(self._queues):
            await q.put(event)
        for handler in list(self._subscribers):
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result

    async def emit_many(self, events: list[BrowserEvent]) -> None:
        for event in events:
            await self.emit(event)

    def history(self, *, event_type: EventType | str | None = None) -> list[BrowserEvent]:
        if event_type is None:
            return list(self._history)
        key = event_type.value if isinstance(event_type, EventType) else event_type
        return [
            e
            for e in self._history
            if (e.event.value if isinstance(e.event, EventType) else e.event) == key
        ]

    def clear_history(self) -> None:
        self._history.clear()

    async def stream(self) -> AsyncIterator[BrowserEvent]:
        """Yield events until the bus is closed."""
        q: asyncio.Queue[BrowserEvent | None] = asyncio.Queue()
        self._queues.append(q)
        try:
            while True:
                item = await q.get()
                if item is None:
                    break
                yield item
        finally:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    async def wait_for(
        self,
        event_type: EventType | str,
        *,
        timeout: float | None = 30.0,
        predicate: Callable[[BrowserEvent], bool] | None = None,
    ) -> BrowserEvent:
        """Block until a matching event is emitted (or timeout)."""
        key = event_type.value if isinstance(event_type, EventType) else event_type
        loop = asyncio.get_running_loop()
        future: asyncio.Future[BrowserEvent] = loop.create_future()

        def _handler(event: BrowserEvent) -> None:
            ev = event.event.value if isinstance(event.event, EventType) else event.event
            if ev != key:
                return
            if predicate is not None and not predicate(event):
                return
            if not future.done():
                future.set_result(event)

        unsub = self.subscribe(_handler)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            unsub()

    async def close(self) -> None:
        self._closed = True
        for q in list(self._queues):
            await q.put(None)
        self._queues.clear()
        self._subscribers.clear()
