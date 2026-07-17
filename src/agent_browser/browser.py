"""Browser session: owns Playwright lifecycle and page factory (M1)."""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

import uuid

from agent_browser.config import BrowserConfig
from agent_browser.exceptions import BrowserNotStartedError, NavigationError
from agent_browser.memory.store import MemoryStore
from agent_browser.page import Page


class Browser:
    """
    Entry point for agent browser sessions.

    M1: wraps Playwright (Chromium / Firefox / WebKit), creates pages,
    and supports ``open(url)`` plus async context-manager lifecycle.
    M7: shared session :class:`MemoryStore`.
    M9: ``create_multi_agent_session()`` helper.
    """

    def __init__(
        self,
        *,
        headless: bool | None = None,
        config: BrowserConfig | None = None,
        session_id: str | None = None,
        memory: MemoryStore | None = None,
        **overrides: object,
    ) -> None:
        self.config = (config or BrowserConfig()).model_copy(deep=True)
        if headless is not None:
            self.config.headless = headless
        for key, value in overrides.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        self.session_id = session_id or str(uuid.uuid4())
        self.memory = memory or MemoryStore(self.session_id)
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._started = False
        self._pages: list[Page] = []

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def pages(self) -> list[Page]:
        """Pages created by this browser that have not been closed."""
        return list(self._pages)

    async def start(self) -> Self:
        """Launch Playwright and a browser context."""
        if self._started:
            return self

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ImportError(
                "playwright is required. Install with: pip install playwright "
                "&& playwright install chromium"
            ) from exc

        self._playwright = await async_playwright().start()
        launcher = getattr(self._playwright, self.config.browser_type)
        self._browser = await launcher.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo_ms,
        )
        context_kwargs: dict[str, Any] = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            "locale": self.config.locale,
        }
        if self.config.user_agent:
            context_kwargs["user_agent"] = self.config.user_agent

        self._context = await self._browser.new_context(**context_kwargs)
        self._context.set_default_timeout(self.config.default_timeout_ms)
        self._started = True
        return self

    async def stop(self) -> None:
        """Close all pages, context, browser, and Playwright."""
        for page in list(self._pages):
            try:
                await page.close()
            except Exception:
                pass
        self._pages.clear()

        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._started = False

    def _ensure_started(self) -> None:
        if not self._started or self._context is None:
            raise BrowserNotStartedError(
                "Browser is not started. Call await browser.start() or use "
                "'async with Browser() as browser:'."
            )

    async def new_page(self) -> Page:
        """Create a new tab/page bound to this session."""
        if not self._started:
            await self.start()
        self._ensure_started()
        assert self._context is not None
        pw_page = await self._context.new_page()
        page = Page(
            pw_page,
            config=self.config,
            on_close=self._forget_page,
            memory=self.memory,
            humanize=bool(getattr(self.config, "humanize", False)),
        )
        self._pages.append(page)
        return page

    def _forget_page(self, page: Page) -> None:
        try:
            self._pages.remove(page)
        except ValueError:
            pass

    async def open(self, url: str, *, wait_until: str = "domcontentloaded") -> Page:
        """Create a page and navigate to ``url``."""
        page = await self.new_page()
        try:
            await page.open(url, wait_until=wait_until)
        except Exception:
            await page.close()
            raise
        return page

    async def set_content(self, html: str, *, wait_until: str = "domcontentloaded") -> Page:
        """
        Create a page with inline HTML (offline / tests).

        Useful for fixtures without network access.
        """
        page = await self.new_page()
        try:
            await page.set_content(html, wait_until=wait_until)
        except Exception as exc:
            await page.close()
            raise NavigationError(f"Failed to set page content: {exc}") from exc
        return page

    def create_multi_agent_session(self) -> Any:
        """Create a MultiAgentSession bound to this browser (M9)."""
        from agent_browser.multiagent.session import MultiAgentSession

        session = MultiAgentSession(session_id=self.session_id, browser=self)
        return session

    async def open_agent(
        self,
        url: str | None = None,
        *,
        detail: str = "normal",
        max_tokens: int = 2000,
    ) -> Any:
        """
        Open a page (optional URL) and return an AgentSession for LLM tool use.
        """
        if url:
            page = await self.open(url)
        else:
            page = await self.new_page()
        return page.as_agent(detail=detail, max_tokens=max_tokens)

    async def __aenter__(self) -> Self:
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.stop()
