"""Browser session: owns Playwright lifecycle and page factory."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from agent_browser.config import BrowserConfig
from agent_browser.page import Page


class Browser:
    """
    Entry point for agent browser sessions.

    M1: wraps Playwright Chromium/Firefox/WebKit.
    Later milestones add multi-agent attach, event bus, shared memory.
    """

    def __init__(
        self,
        *,
        headless: bool | None = None,
        config: BrowserConfig | None = None,
        **overrides: object,
    ) -> None:
        self.config = config or BrowserConfig()
        if headless is not None:
            self.config.headless = headless
        for key, value in overrides.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        self._playwright = None
        self._browser = None
        self._context = None
        self._started = False

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
        context_kwargs: dict[str, object] = {
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
        """Close context, browser, and Playwright."""
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._started = False

    async def new_page(self) -> Page:
        """Create a new tab/page bound to this session."""
        if not self._started:
            await self.start()
        assert self._context is not None
        pw_page = await self._context.new_page()
        return Page(pw_page, config=self.config)

    async def open(self, url: str) -> Page:
        """Create a page and navigate to ``url``."""
        page = await self.new_page()
        await page.open(url)
        return page

    async def __aenter__(self) -> Self:
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.stop()
