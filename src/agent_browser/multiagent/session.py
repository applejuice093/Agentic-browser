"""Multi-agent session orchestration (M9)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from typing import Any

from agent_browser.events.bus import EventBus, EventHandler
from agent_browser.models.events import BrowserEvent, EventType


class AgentHandle:
    """
    Lightweight handle for an agent attached to a shared session.

    Agents share the underlying Browser/Page but can filter event streams
    and hold private metadata. Commands are serialized via the session lock.
    """

    def __init__(
        self,
        agent_id: str,
        session: MultiAgentSession,
        *,
        role: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.session = session
        self.role = role
        self.metadata = metadata or {}
        self._unsubs: list[Callable[[], None]] = []

    @property
    def browser(self) -> Any:
        return self.session.browser

    @property
    def page(self) -> Any:
        return self.session.page

    def subscribe(
        self,
        handler: EventHandler,
        *,
        event_type: EventType | str | None = None,
    ) -> Callable[[], None]:
        """Subscribe to session events (optionally filtered by type)."""

        def _wrapped(event: BrowserEvent) -> Any:
            if event_type is not None:
                key = event_type.value if isinstance(event_type, EventType) else event_type
                ev = event.event.value if isinstance(event.event, EventType) else event.event
                if ev != key:
                    return None
            # Tag event data with recipient (non-mutating copy for handler)
            return handler(event)

        unsub = self.session.events.subscribe(_wrapped)
        self._unsubs.append(unsub)
        return unsub

    async def run(self, coro: Any) -> Any:
        """Run a coroutine while holding the session command lock."""
        async with self.session.lock:
            return await coro

    def detach(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        self.session.detach(self.agent_id)


class MultiAgentSession:
    """
    Coordinate multiple agents on a shared browser session.

    - One Browser / optional primary Page
    - Shared EventBus (also mirrors page events when a page is bound)
    - asyncio.Lock serializes mutating commands to avoid races
    """

    def __init__(
        self,
        session_id: str | None = None,
        *,
        browser: Any | None = None,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.browser = browser
        self.page: Any | None = None
        self.agents: dict[str, AgentHandle] = {}
        self.events = EventBus()
        self.lock = asyncio.Lock()
        self._page_unsub: Callable[[], None] | None = None

    def attach(
        self,
        agent_id: str | None = None,
        *,
        role: str = "general",
        metadata: dict[str, Any] | None = None,
        handle: Any | None = None,
    ) -> AgentHandle:
        """Register an agent. ``handle`` is accepted for backward compatibility."""
        if handle is not None and not isinstance(handle, AgentHandle):
            # legacy: store opaque handle
            aid = agent_id or str(uuid.uuid4())
            agent = AgentHandle(aid, self, role=role, metadata=metadata)
            self.agents[aid] = agent
            return agent
        aid = agent_id or str(uuid.uuid4())
        if aid in self.agents:
            raise ValueError(f"Agent {aid!r} already attached")
        agent = AgentHandle(aid, self, role=role, metadata=metadata)
        self.agents[aid] = agent
        return agent

    def detach(self, agent_id: str) -> None:
        agent = self.agents.pop(agent_id, None)
        if agent is not None:
            for u in list(agent._unsubs):  # noqa: SLF001
                u()
            agent._unsubs.clear()  # noqa: SLF001

    def list_agents(self) -> list[str]:
        return list(self.agents.keys())

    def get_agent(self, agent_id: str) -> AgentHandle | None:
        return self.agents.get(agent_id)

    def agents_by_role(self, role: str) -> list[AgentHandle]:
        return [a for a in self.agents.values() if a.role == role]

    def bind_browser(self, browser: Any) -> None:
        self.browser = browser

    def bind_page(self, page: Any) -> None:
        """Bind a Page and mirror its events onto the session bus."""
        if self._page_unsub is not None:
            self._page_unsub()
            self._page_unsub = None
        self.page = page

        def _mirror(event: BrowserEvent) -> None:
            # schedule emit if loop running; sync path uses create_task
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.events.emit(event))
            except RuntimeError:
                pass

        self._page_unsub = page.on(_mirror)

    async def broadcast(self, event: BrowserEvent) -> None:
        await self.events.emit(event)

    async def close(self) -> None:
        for aid in list(self.agents.keys()):
            self.detach(aid)
        if self._page_unsub:
            self._page_unsub()
            self._page_unsub = None
        await self.events.close()
