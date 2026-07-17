"""Page API: navigation, actions, and snapshots."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agent_browser.models.element import Element
from agent_browser.models.snapshot import Snapshot

if TYPE_CHECKING:
    from playwright.async_api import Page as PlaywrightPage

    from agent_browser.config import BrowserConfig


class Page:
    """
    High-level page handle for agents.

    M1 implements open/click/type/snapshot (raw + basic structure).
    Later milestones extend find(), diffs, network, memory, etc.
    """

    def __init__(self, pw_page: PlaywrightPage, *, config: BrowserConfig) -> None:
        self._page = pw_page
        self.config = config
        self._next_element_id = 1

    @property
    def url(self) -> str:
        return self._page.url

    async def open(self, url: str, *, wait_until: str = "domcontentloaded") -> None:
        """Navigate to a URL."""
        await self._page.goto(url, wait_until=wait_until)

    async def click(
        self,
        target: int | Element | str,
        *,
        delay_ms: float | None = None,
    ) -> None:
        """
        Click an element by stable id, Element, or CSS selector (M1 fallback).

        Prefer stable IDs once M2 semantic model is live.
        """
        locator = await self._resolve_locator(target)
        kwargs: dict[str, Any] = {}
        if delay_ms is not None:
            kwargs["delay"] = delay_ms
        await locator.click(**kwargs)

    async def type(
        self,
        target: int | Element | str,
        text: str,
        *,
        delay_ms: float | None = None,
        clear: bool = False,
    ) -> None:
        """Type into an input by id, Element, or selector."""
        locator = await self._resolve_locator(target)
        if clear:
            await locator.fill("")
        kwargs: dict[str, Any] = {}
        if delay_ms is not None:
            kwargs["delay"] = delay_ms
        await locator.type(text, **kwargs)

    async def fill(self, target: int | Element | str, text: str) -> None:
        """Fill an input (clears existing value)."""
        locator = await self._resolve_locator(target)
        await locator.fill(text)

    async def snapshot(self, *, include_raw_html: bool = False) -> Snapshot:
        """
        Capture current page state.

        M1: title/url + lightweight interactive element list from DOM.
        M2+: full semantic + accessibility merge.
        """
        title = await self._page.title()
        url = self._page.url
        elements = await self._extract_basic_elements()
        raw_html: str | None = None
        if include_raw_html:
            raw_html = await self._page.content()

        return Snapshot(
            url=url,
            title=title,
            elements=elements,
            raw_html=raw_html,
        )

    async def wait_for_load_state(self, state: str = "domcontentloaded") -> None:
        await self._page.wait_for_load_state(state)

    async def wait_for_navigation(self) -> None:
        await self._page.wait_for_load_state("networkidle")

    async def evaluate(self, expression: str) -> Any:
        """Run JS in the page context."""
        return await self._page.evaluate(expression)

    async def close(self) -> None:
        await self._page.close()

    # --- internal helpers ---

    async def _resolve_locator(self, target: int | Element | str) -> Any:
        if isinstance(target, Element):
            # M2: resolve by data-agent-id; until then fall back if attribute present
            sel = f'[data-agent-id="{target.id}"]'
            loc = self._page.locator(sel)
            if await loc.count() > 0:
                return loc.first
            if target.attributes.get("id"):
                return self._page.locator(f'#{target.attributes["id"]}')
            raise ValueError(f"Cannot resolve element id={target.id} without locator")

        if isinstance(target, int):
            sel = f'[data-agent-id="{target}"]'
            loc = self._page.locator(sel)
            if await loc.count() == 0:
                raise ValueError(f"No element with stable id={target}")
            return loc.first

        # CSS / text selector string
        return self._page.locator(target)

    async def _extract_basic_elements(self) -> list[Element]:
        """M1: extract interactive-ish nodes from the live DOM."""
        script = """
        () => {
          const interactive = document.querySelectorAll(
            'a, button, input, select, textarea, [role], [onclick]'
          );
          const out = [];
          let id = 1;
          for (const el of interactive) {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            const visible =
              style.display !== 'none' &&
              style.visibility !== 'hidden' &&
              rect.width > 0 &&
              rect.height > 0;
            const attrs = {};
            for (const a of el.attributes) {
              attrs[a.name] = a.value;
            }
            el.setAttribute('data-agent-id', String(id));
            out.push({
              id: id,
              role: el.getAttribute('role') || el.tagName.toLowerCase(),
              type: el.tagName.toLowerCase(),
              text: (el.innerText || el.textContent || '').trim().slice(0, 200),
              attributes: attrs,
              value: el.value !== undefined ? String(el.value) : null,
              checked: el.checked !== undefined ? Boolean(el.checked) : null,
              visible: visible,
              enabled: !el.disabled,
              bounding_box: {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
              },
              name: el.getAttribute('aria-label') || el.getAttribute('name') || null,
            });
            id += 1;
          }
          return out;
        }
        """
        raw = await self._page.evaluate(script)
        self._next_element_id = len(raw) + 1
        return [Element.model_validate(item) for item in raw]
