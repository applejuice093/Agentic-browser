"""Page API: navigation, actions, and semantic snapshots (M1 + M2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from agent_browser.exceptions import ElementNotFoundError, NavigationError, SnapshotError
from agent_browser.models.element import Element
from agent_browser.models.snapshot import Snapshot
from agent_browser.semantic.engine import SemanticDOMEngine

if TYPE_CHECKING:
    from playwright.async_api import Page as PlaywrightPage

    from agent_browser.config import BrowserConfig

WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]


class Page:
    """
    High-level page handle for agents.

    M1: ``open``, ``click``, ``type`` / ``fill``, raw HTML.
    M2: semantic ``snapshot()``, stable IDs across updates, ``find`` / ``find_all``.
    """

    def __init__(
        self,
        pw_page: PlaywrightPage,
        *,
        config: BrowserConfig,
        on_close: Callable[[Page], None] | None = None,
    ) -> None:
        self._page = pw_page
        self.config = config
        self._on_close = on_close
        self._closed = False
        self._element_registry: dict[int, Element] = {}
        self._semantic = SemanticDOMEngine()

    # --- properties ---

    @property
    def url(self) -> str:
        if self._closed:
            return "about:blank"
        return self._page.url

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def playwright_page(self) -> PlaywrightPage:
        """Underlying Playwright page (escape hatch)."""
        return self._page

    @property
    def semantic(self) -> SemanticDOMEngine:
        """Access the semantic DOM engine for advanced queries."""
        return self._semantic

    # --- navigation ---

    async def open(self, url: str, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        """Navigate to a URL (alias of :meth:`goto`)."""
        await self.goto(url, wait_until=wait_until)

    async def goto(self, url: str, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        """Navigate to a URL."""
        self._ensure_open()
        try:
            await self._page.goto(url, wait_until=wait_until)
        except Exception as exc:
            raise NavigationError(f"Navigation to {url!r} failed: {exc}") from exc
        self._on_document_reset()

    async def set_content(
        self,
        html: str,
        *,
        wait_until: WaitUntil = "domcontentloaded",
    ) -> None:
        """Load inline HTML into the page (no network)."""
        self._ensure_open()
        try:
            await self._page.set_content(html, wait_until=wait_until)
        except Exception as exc:
            raise NavigationError(f"set_content failed: {exc}") from exc
        self._on_document_reset()

    async def reload(self, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        self._ensure_open()
        try:
            await self._page.reload(wait_until=wait_until)
        except Exception as exc:
            raise NavigationError(f"Reload failed: {exc}") from exc
        self._on_document_reset()

    async def go_back(self, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        self._ensure_open()
        await self._page.go_back(wait_until=wait_until)
        self._on_document_reset()

    async def go_forward(self, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        self._ensure_open()
        await self._page.go_forward(wait_until=wait_until)
        self._on_document_reset()

    # --- actions ---

    async def click(
        self,
        target: int | Element | str,
        *,
        delay_ms: float | None = None,
        timeout_ms: float | None = None,
    ) -> None:
        """
        Click an element by stable id, Element, or CSS selector.

        Prefer stable IDs from the latest :meth:`snapshot`.
        """
        locator = await self._resolve_locator(target)
        kwargs: dict[str, Any] = {}
        if delay_ms is not None:
            kwargs["delay"] = delay_ms
        if timeout_ms is not None:
            kwargs["timeout"] = timeout_ms
        try:
            await locator.click(**kwargs)
        except Exception as exc:
            raise ElementNotFoundError(f"Click failed for target {target!r}: {exc}") from exc

    async def type(
        self,
        target: int | Element | str,
        text: str,
        *,
        delay_ms: float | None = None,
        clear: bool = False,
        timeout_ms: float | None = None,
    ) -> None:
        """Type into an input by id, Element, or selector (keystroke simulation)."""
        locator = await self._resolve_locator(target)
        timeout = timeout_ms
        try:
            if clear:
                await locator.fill("", timeout=timeout)
            if hasattr(locator, "press_sequentially"):
                kwargs: dict[str, Any] = {}
                if delay_ms is not None:
                    kwargs["delay"] = delay_ms
                if timeout is not None:
                    kwargs["timeout"] = timeout
                await locator.press_sequentially(text, **kwargs)
            else:
                kwargs = {}
                if delay_ms is not None:
                    kwargs["delay"] = delay_ms
                if timeout is not None:
                    kwargs["timeout"] = timeout
                await locator.type(text, **kwargs)
        except Exception as exc:
            raise ElementNotFoundError(f"Type failed for target {target!r}: {exc}") from exc

    async def fill(
        self,
        target: int | Element | str,
        text: str,
        *,
        timeout_ms: float | None = None,
    ) -> None:
        """Fill an input (clears existing value in one shot)."""
        locator = await self._resolve_locator(target)
        kwargs: dict[str, Any] = {}
        if timeout_ms is not None:
            kwargs["timeout"] = timeout_ms
        try:
            await locator.fill(text, **kwargs)
        except Exception as exc:
            raise ElementNotFoundError(f"Fill failed for target {target!r}: {exc}") from exc

    async def press(
        self,
        target: int | Element | str,
        key: str,
        *,
        timeout_ms: float | None = None,
    ) -> None:
        """Press a keyboard key on a target (e.g. ``Enter``, ``Tab``)."""
        locator = await self._resolve_locator(target)
        kwargs: dict[str, Any] = {}
        if timeout_ms is not None:
            kwargs["timeout"] = timeout_ms
        try:
            await locator.press(key, **kwargs)
        except Exception as exc:
            raise ElementNotFoundError(f"Press failed for target {target!r}: {exc}") from exc

    async def select_option(
        self,
        target: int | Element | str,
        value: str | list[str],
        *,
        timeout_ms: float | None = None,
    ) -> None:
        """Select option(s) on a ``<select>`` element."""
        locator = await self._resolve_locator(target)
        kwargs: dict[str, Any] = {}
        if timeout_ms is not None:
            kwargs["timeout"] = timeout_ms
        try:
            await locator.select_option(value, **kwargs)
        except Exception as exc:
            raise ElementNotFoundError(f"select_option failed for {target!r}: {exc}") from exc

    # --- inspection ---

    async def snapshot(
        self,
        *,
        include_raw_html: bool = False,
        merge_accessibility: bool = True,
    ) -> Snapshot:
        """
        Capture a semantic page snapshot.

        Includes role/name, stable ids, parent/child links, and optional raw HTML.
        IDs remain stable across in-page updates until the next navigation.
        """
        self._ensure_open()
        try:
            title = await self._page.title()
            url = self._page.url
            scroll_position = await self._page.evaluate(
                "() => window.scrollY || document.documentElement.scrollTop || 0"
            )
            snap = await self._semantic.capture(
                self._page,
                url=url,
                title=title,
                scroll_position=float(scroll_position or 0),
                include_raw_html=include_raw_html,
                merge_accessibility=merge_accessibility,
            )
        except Exception as exc:
            raise SnapshotError(f"Failed to capture snapshot: {exc}") from exc

        self._element_registry = {el.id: el for el in snap.elements}
        return snap

    async def find(
        self,
        *,
        role: str | None = None,
        text_contains: str | None = None,
        name: str | None = None,
        type: str | None = None,  # noqa: A002
        visible_only: bool = True,
        refresh: bool = True,
    ) -> Element | None:
        """
        Find the first semantic element matching the given criteria.

        If ``refresh`` is True (default), takes a fresh snapshot first.
        """
        matches = await self.find_all(
            role=role,
            text_contains=text_contains,
            name=name,
            type=type,
            visible_only=visible_only,
            refresh=refresh,
        )
        return matches[0] if matches else None

    async def find_all(
        self,
        *,
        role: str | None = None,
        text_contains: str | None = None,
        name: str | None = None,
        type: str | None = None,  # noqa: A002
        visible_only: bool = True,
        refresh: bool = True,
    ) -> list[Element]:
        """Find all semantic elements matching the given criteria."""
        if refresh or not self._element_registry:
            await self.snapshot()
        return self._semantic.query(
            role=role,
            text_contains=text_contains,
            name=name,
            type=type,
            visible_only=visible_only,
        )

    async def get_element(self, element_id: int, *, refresh: bool = False) -> Element | None:
        """Return a previously snapshotted element by stable id."""
        if refresh:
            await self.snapshot()
        return self._semantic.get(element_id) or self._element_registry.get(element_id)

    async def content(self) -> str:
        """Return raw HTML of the current page."""
        self._ensure_open()
        return await self._page.content()

    async def title(self) -> str:
        self._ensure_open()
        return await self._page.title()

    async def get_text(self, target: int | Element | str) -> str:
        """Visible text content of a target element."""
        locator = await self._resolve_locator(target)
        try:
            text = await locator.inner_text()
        except Exception as exc:
            raise ElementNotFoundError(f"get_text failed for {target!r}: {exc}") from exc
        return text.strip()

    async def get_value(self, target: int | Element | str) -> str:
        """Input value of a form control."""
        locator = await self._resolve_locator(target)
        try:
            value = await locator.input_value()
        except Exception as exc:
            raise ElementNotFoundError(f"get_value failed for {target!r}: {exc}") from exc
        return value

    async def wait_for_selector(
        self,
        selector: str,
        *,
        state: Literal["attached", "detached", "hidden", "visible"] = "visible",
        timeout_ms: float | None = None,
    ) -> None:
        self._ensure_open()
        kwargs: dict[str, Any] = {"state": state}
        if timeout_ms is not None:
            kwargs["timeout"] = timeout_ms
        await self._page.wait_for_selector(selector, **kwargs)

    async def wait_for_load_state(
        self,
        state: Literal["domcontentloaded", "load", "networkidle"] = "domcontentloaded",
    ) -> None:
        self._ensure_open()
        await self._page.wait_for_load_state(state)

    async def wait_for_navigation(self) -> None:
        """Wait until network is idle (best-effort after an action)."""
        await self.wait_for_load_state("networkidle")

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        """Run JS in the page context."""
        self._ensure_open()
        if arg is None:
            return await self._page.evaluate(expression)
        return await self._page.evaluate(expression, arg)

    async def screenshot(self, *, path: str | None = None, full_page: bool = False) -> bytes:
        """Take a PNG screenshot; optionally write to ``path``."""
        self._ensure_open()
        kwargs: dict[str, Any] = {"full_page": full_page, "type": "png"}
        if path is not None:
            kwargs["path"] = path
        return await self._page.screenshot(**kwargs)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._element_registry.clear()
        self._semantic.reset()
        try:
            await self._page.close()
        except Exception:
            pass
        if self._on_close is not None:
            self._on_close(self)

    # --- internal helpers ---

    def _on_document_reset(self) -> None:
        """Navigation/document replacement invalidates identity maps."""
        self._element_registry.clear()
        self._semantic.reset()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Page is closed")

    async def _resolve_locator(self, target: int | Element | str) -> Any:
        self._ensure_open()

        if isinstance(target, Element):
            return await self._resolve_locator(target.id)

        if isinstance(target, int):
            sel = f'[data-agent-id="{target}"]'
            loc = self._page.locator(sel)
            count = await loc.count()
            if count > 0:
                return loc.first
            el = self._element_registry.get(target) or self._semantic.get(target)
            if el is not None:
                html_id = el.attributes.get("id")
                if html_id:
                    by_id = self._page.locator(f"#{html_id}")
                    if await by_id.count() > 0:
                        return by_id.first
                name = el.attributes.get("name") or el.name
                if name and el.type in ("input", "textarea", "select", "button"):
                    by_name = self._page.locator(f'{el.type}[name="{name}"]')
                    if await by_name.count() > 0:
                        return by_name.first
            raise ElementNotFoundError(
                f"No element with stable id={target}. "
                "Call page.snapshot() first, or pass a CSS selector."
            )

        return self._page.locator(target)
