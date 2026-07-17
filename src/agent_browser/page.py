"""Page API: navigation, actions, semantic snapshots, diffs & events (M1–M3)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

import asyncio
import random

from agent_browser.accessibility.queries import (
    Exactness,
    filter_by_label,
    filter_by_placeholder,
    filter_by_role,
    filter_by_test_id,
    filter_by_text,
)
from agent_browser.antibot.humanize import HumanizedInput, Point
from agent_browser.events.bus import EventBus, EventHandler
from agent_browser.events.diffing import DiffEngine
from agent_browser.events.monitor import MutationMonitor
from agent_browser.exceptions import ElementNotFoundError, NavigationError, SnapshotError
from agent_browser.models.diff import Diff
from agent_browser.models.element import Element
from agent_browser.models.events import BrowserEvent, EventType
from agent_browser.models.snapshot import Snapshot
from agent_browser.models.network import NetworkRequest
from agent_browser.models.vision import OCRRegion, VisionDetection, VisionResult
from agent_browser.memory.store import MemoryStore
from agent_browser.network.monitor import NetworkMonitor
from agent_browser.planning.context import ContextBuilder
from agent_browser.planning.planner import Planner
from agent_browser.semantic.engine import SemanticDOMEngine
from agent_browser.vision.engine import VisionEngine

if TYPE_CHECKING:
    from playwright.async_api import Page as PlaywrightPage

    from agent_browser.config import BrowserConfig

WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]


class Page:
    """
    High-level page handle for agents.

    M1: ``open``, ``click``, ``type`` / ``fill``, raw HTML.
    M2: semantic ``snapshot()``, stable IDs, ``find`` / ``find_all``.
    M3: incremental ``diff``, event bus, MutationObserver ``watch``.
    M4: OCR / vision (``get_text_in_screenshot``, ``detect_ui``).
    M5: network capture, ``wait_for_api``, GraphQL detection.
    M6: ``get_by_role`` / ``get_by_label`` accessibility finders.
    M7: session memory, ``context()``, ``plan(goal)``.
    M8: optional humanized mouse/keyboard input.
    Agent-native: :meth:`as_agent` → compact observe/act loop for LLMs.
    """

    def __init__(
        self,
        pw_page: PlaywrightPage,
        *,
        config: BrowserConfig,
        on_close: Callable[[Page], None] | None = None,
        memory: MemoryStore | None = None,
        humanize: HumanizedInput | bool | None = None,
        network: NetworkMonitor | None = None,
    ) -> None:
        self._page = pw_page
        self.config = config
        self._on_close = on_close
        self._closed = False
        self._element_registry: dict[int, Element] = {}
        self._semantic = SemanticDOMEngine()
        self._events = EventBus()
        self._diff_engine = DiffEngine()
        self._vision = VisionEngine()
        self._network = network or NetworkMonitor()
        self._memory = memory or MemoryStore()
        self._context_builder = ContextBuilder()
        self._planner = Planner()
        if isinstance(humanize, HumanizedInput):
            self._humanize = humanize
        else:
            enabled = (
                bool(humanize)
                if humanize is not None
                else bool(getattr(config, "humanize", False))
            )
            self._humanize = HumanizedInput(
                enabled=enabled,
                min_delay_ms=getattr(config, "humanize_min_delay_ms", 30),
                max_delay_ms=getattr(config, "humanize_max_delay_ms", 120),
            )
        self._last_snapshot: Snapshot | None = None
        self._last_diff: Diff | None = None
        self._last_vision: VisionResult | None = None
        self._mutation = MutationMonitor(debounce_ms=100)
        self._auto_snapshot_on_mutation = True
        self._watch_enabled = False
        self._nav_from_url: str | None = None
        self._mouse_pos = Point(0, 0)
        self._network_ready = False

        # Playwright navigation hook
        self._page.on("framenavigated", self._on_frame_navigated)

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

    @property
    def events(self) -> EventBus:
        """Page event bus (M3)."""
        return self._events

    @property
    def last_snapshot(self) -> Snapshot | None:
        return self._last_snapshot

    @property
    def last_diff(self) -> Diff | None:
        """Diff from the most recent snapshot vs the previous one."""
        return self._last_diff

    @property
    def vision(self) -> VisionEngine:
        """Vision / OCR engine (M4)."""
        return self._vision

    @property
    def last_vision(self) -> VisionResult | None:
        """Result of the most recent vision pass."""
        return self._last_vision

    @property
    def memory(self) -> MemoryStore:
        """Session memory store (M7)."""
        return self._memory

    @property
    def humanize(self) -> HumanizedInput:
        """Humanized input controller (M8)."""
        return self._humanize

    @property
    def network(self) -> NetworkMonitor:
        """Network monitor (M5)."""
        return self._network

    def set_humanize(self, enabled: bool) -> None:
        self._humanize.enabled = enabled

    async def _ensure_network(self) -> None:
        if self._network_ready:
            return
        self._network.set_event_emitter(self._events.emit)
        await self._network.attach(self._page)
        self._network_ready = True

    # --- navigation ---

    async def open(self, url: str, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        """Navigate to a URL (alias of :meth:`goto`)."""
        await self.goto(url, wait_until=wait_until)

    async def goto(self, url: str, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        """Navigate to a URL."""
        self._ensure_open()
        await self._ensure_network()
        from_url = self._page.url
        self._nav_from_url = from_url
        try:
            await self._page.goto(url, wait_until=wait_until)
        except Exception as exc:
            raise NavigationError(f"Navigation to {url!r} failed: {exc}") from exc
        self._on_document_reset()
        await self._events.emit(
            BrowserEvent.make(
                EventType.NAVIGATION,
                from_url=from_url,
                to_url=self._page.url,
                via="goto",
            )
        )
        self._memory.log_url(self._page.url)
        self._memory.log_action({"type": "goto", "url": self._page.url})
        if self._watch_enabled:
            await self._reattach_mutation_observer()

    async def set_content(
        self,
        html: str,
        *,
        wait_until: WaitUntil = "domcontentloaded",
    ) -> None:
        """Load inline HTML into the page (no network)."""
        self._ensure_open()
        await self._ensure_network()
        from_url = self._page.url
        try:
            await self._page.set_content(html, wait_until=wait_until)
        except Exception as exc:
            raise NavigationError(f"set_content failed: {exc}") from exc
        self._on_document_reset()
        await self._events.emit(
            BrowserEvent.make(
                EventType.NAVIGATION,
                from_url=from_url,
                to_url=self._page.url,
                via="set_content",
            )
        )
        if self._watch_enabled:
            await self._reattach_mutation_observer()

    async def reload(self, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        self._ensure_open()
        from_url = self._page.url
        try:
            await self._page.reload(wait_until=wait_until)
        except Exception as exc:
            raise NavigationError(f"Reload failed: {exc}") from exc
        self._on_document_reset()
        await self._events.emit(
            BrowserEvent.make(
                EventType.NAVIGATION,
                from_url=from_url,
                to_url=self._page.url,
                via="reload",
            )
        )
        if self._watch_enabled:
            await self._reattach_mutation_observer()

    async def go_back(self, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        self._ensure_open()
        from_url = self._page.url
        await self._page.go_back(wait_until=wait_until)
        self._on_document_reset()
        await self._events.emit(
            BrowserEvent.make(
                EventType.NAVIGATION,
                from_url=from_url,
                to_url=self._page.url,
                via="back",
            )
        )
        if self._watch_enabled:
            await self._reattach_mutation_observer()

    async def go_forward(self, *, wait_until: WaitUntil = "domcontentloaded") -> None:
        self._ensure_open()
        from_url = self._page.url
        await self._page.go_forward(wait_until=wait_until)
        self._on_document_reset()
        await self._events.emit(
            BrowserEvent.make(
                EventType.NAVIGATION,
                from_url=from_url,
                to_url=self._page.url,
                via="forward",
            )
        )
        if self._watch_enabled:
            await self._reattach_mutation_observer()

    # --- actions ---

    async def click(
        self,
        target: int | Element | str,
        *,
        delay_ms: float | None = None,
        timeout_ms: float | None = None,
        humanize: bool | None = None,
    ) -> None:
        """
        Click an element by stable id, Element, or CSS selector.

        Prefer stable IDs from the latest :meth:`snapshot`.
        When humanize is on, moves the mouse along a curved path first.
        """
        locator = await self._resolve_locator(target)
        use_h = self._humanize.enabled if humanize is None else humanize
        kwargs: dict[str, Any] = {}
        if delay_ms is not None:
            kwargs["delay"] = delay_ms
        elif use_h:
            kwargs["delay"] = self._humanize.click_delay_ms()
        if timeout_ms is not None:
            kwargs["timeout"] = timeout_ms
        try:
            if use_h:
                await self._human_move_to_locator(locator)
            await locator.click(**kwargs)
        except Exception as exc:
            raise ElementNotFoundError(f"Click failed for target {target!r}: {exc}") from exc
        await self._events.emit(
            BrowserEvent.make(
                EventType.ELEMENT_CLICKED,
                target=self._target_meta(target),
            )
        )
        self._memory.log_action({"type": "click", "target": self._target_meta(target)})

    async def type(
        self,
        target: int | Element | str,
        text: str,
        *,
        delay_ms: float | None = None,
        clear: bool = False,
        timeout_ms: float | None = None,
        humanize: bool | None = None,
    ) -> None:
        """Type into an input by id, Element, or selector (keystroke simulation)."""
        locator = await self._resolve_locator(target)
        timeout = timeout_ms
        use_h = self._humanize.enabled if humanize is None else humanize
        try:
            if clear:
                await locator.fill("", timeout=timeout)
            if use_h and delay_ms is None:
                # Character-level delays
                await locator.click(timeout=timeout)
                for ch, d in zip(text, self._humanize.typing_profile(text), strict=False):
                    await self._page.keyboard.type(ch, delay=d)
            elif hasattr(locator, "press_sequentially"):
                kwargs: dict[str, Any] = {}
                if delay_ms is not None:
                    kwargs["delay"] = delay_ms
                elif use_h:
                    kwargs["delay"] = self._humanize.keystroke_delay_ms()
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
        await self._events.emit(
            BrowserEvent.make(
                EventType.ELEMENT_TYPED,
                target=self._target_meta(target),
                length=len(text),
            )
        )
        self._memory.log_action(
            {"type": "type", "target": self._target_meta(target), "length": len(text)}
        )

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
        await self._events.emit(
            BrowserEvent.make(
                EventType.ELEMENT_FILLED,
                target=self._target_meta(target),
                length=len(text),
            )
        )
        self._memory.log_action(
            {
                "type": "fill",
                "target": self._target_meta(target),
                "length": len(text),
                "value": text,
            }
        )

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
        emit_events: bool = True,
    ) -> Snapshot:
        """
        Capture a semantic page snapshot.

        When a previous snapshot exists, computes an incremental :class:`Diff`
        (available as :attr:`last_diff`) and optionally emits fine-grained events.
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

        previous = self._last_snapshot
        self._element_registry = {el.id: el for el in snap.elements}
        self._last_snapshot = snap

        if previous is not None:
            diff = self._diff_engine.diff(previous, snap)
            self._last_diff = diff
            if emit_events and not diff.is_empty:
                await self._events.emit_many(self._diff_engine.to_events(diff))
        else:
            self._last_diff = Diff(
                current_url=snap.url,
                previous_url=None,
            )
            if emit_events:
                await self._events.emit(
                    BrowserEvent.make(
                        EventType.SNAPSHOT,
                        url=snap.url,
                        title=snap.title,
                        element_count=len(snap.elements),
                    )
                )

        return snap

    def diff_snapshots(self, previous: Snapshot, current: Snapshot) -> Diff:
        """Compute a diff between two snapshots without side effects."""
        return self._diff_engine.diff(previous, current)

    async def refresh_diff(self, *, emit_events: bool = True) -> Diff:
        """Take a new snapshot and return the diff vs the previous one."""
        await self.snapshot(emit_events=emit_events)
        return self._last_diff or Diff()

    # --- events / watch (M3) ---

    def on(self, handler: EventHandler) -> Callable[[], None]:
        """Subscribe to all page events; returns unsubscribe callable."""
        return self._events.subscribe(handler)

    def on_event(
        self,
        event_type: EventType | str,
        handler: EventHandler,
    ) -> Callable[[], None]:
        """Subscribe to a single event type."""
        key = event_type.value if isinstance(event_type, EventType) else event_type

        def _wrapped(event: BrowserEvent) -> Any:
            ev = event.event.value if isinstance(event.event, EventType) else event.event
            if ev == key:
                return handler(event)
            return None

        return self._events.subscribe(_wrapped)

    async def wait_for_event(
        self,
        event_type: EventType | str,
        *,
        timeout: float | None = 30.0,
    ) -> BrowserEvent:
        """Wait until an event of the given type is emitted."""
        return await self._events.wait_for(event_type, timeout=timeout)

    async def watch(
        self,
        *,
        enabled: bool = True,
        debounce_ms: int = 100,
        auto_snapshot: bool = True,
    ) -> None:
        """
        Enable or disable MutationObserver-based live updates.

        When enabled, DOM mutations emit ``mutation`` events and (if
        ``auto_snapshot``) a follow-up semantic snapshot + diff stream.
        """
        self._ensure_open()
        self._auto_snapshot_on_mutation = auto_snapshot
        self._mutation.debounce_ms = debounce_ms

        if not enabled:
            await self._mutation.detach()
            self._watch_enabled = False
            return

        await self._mutation.attach(self._page, on_mutation=self._handle_mutation)
        self._watch_enabled = True

    @property
    def is_watching(self) -> bool:
        return self._watch_enabled and self._mutation.is_attached

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

    # --- accessibility finders (M6) ---

    async def get_by_role(
        self,
        role: str,
        *,
        name: str | None = None,
        exact: bool = False,
        visible_only: bool = True,
        refresh: bool = True,
    ) -> Element | None:
        """Playwright-style role finder against the semantic model."""
        matches = await self.get_all_by_role(
            role, name=name, exact=exact, visible_only=visible_only, refresh=refresh
        )
        return matches[0] if matches else None

    async def get_all_by_role(
        self,
        role: str,
        *,
        name: str | None = None,
        exact: bool = False,
        visible_only: bool = True,
        refresh: bool = True,
    ) -> list[Element]:
        if refresh or not self._element_registry:
            await self.snapshot()
        return filter_by_role(
            list(self._element_registry.values()),
            role,
            name=name,
            exact=exact,
            visible_only=visible_only,
        )

    async def get_by_label(
        self,
        label: str,
        *,
        exact: bool = False,
        refresh: bool = True,
    ) -> Element | None:
        """Find a control by associated label / accessible name."""
        matches = await self.get_all_by_label(label, exact=exact, refresh=refresh)
        return matches[0] if matches else None

    async def get_all_by_label(
        self,
        label: str,
        *,
        exact: bool = False,
        refresh: bool = True,
    ) -> list[Element]:
        if refresh or not self._element_registry:
            await self.snapshot()
        match: Exactness = "exact" if exact else "contains"
        return filter_by_label(
            list(self._element_registry.values()), label, match=match
        )

    async def get_by_placeholder(
        self,
        placeholder: str,
        *,
        exact: bool = False,
        refresh: bool = True,
    ) -> Element | None:
        if refresh or not self._element_registry:
            await self.snapshot()
        match: Exactness = "exact" if exact else "contains"
        found = filter_by_placeholder(
            list(self._element_registry.values()), placeholder, match=match
        )
        return found[0] if found else None

    async def get_by_text(
        self,
        text: str,
        *,
        exact: bool = False,
        refresh: bool = True,
    ) -> Element | None:
        if refresh or not self._element_registry:
            await self.snapshot()
        match: Exactness = "exact" if exact else "contains"
        found = filter_by_text(list(self._element_registry.values()), text, match=match)
        return found[0] if found else None

    async def get_by_test_id(
        self,
        test_id: str,
        *,
        attr: str = "data-testid",
        refresh: bool = True,
    ) -> Element | None:
        if refresh or not self._element_registry:
            await self.snapshot()
        found = filter_by_test_id(
            list(self._element_registry.values()), test_id, attr=attr
        )
        return found[0] if found else None

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

    # --- vision / OCR (M4) ---

    async def get_text_in_screenshot(
        self,
        *,
        region: tuple[float, float, float, float] | None = None,
        full_page: bool = False,
        lang: str | None = None,
        image_bytes: bytes | None = None,
    ) -> list[dict[str, Any]]:
        """
        OCR text regions from a page screenshot (design-report API).

        Args:
            region: Optional ``(x, y, width, height)`` crop in CSS pixels.
            full_page: Capture full scrollable page when taking a new screenshot.
            lang: Tesseract language code (default engine lang, usually ``eng``).
            image_bytes: Reuse an existing PNG/JPEG instead of capturing again.

        Returns:
            List of ``{x, y, width, height, text, confidence}`` dicts.
        """
        self._ensure_open()
        if image_bytes is None:
            image_bytes = await self.screenshot(full_page=full_page)
        regions = await self._vision.get_text_in_screenshot(
            image_bytes, region=region, lang=lang
        )
        self._last_vision = VisionResult(
            ocr_regions=[OCRRegion.model_validate(r) for r in regions],
            engine="tesseract",
        )
        return regions

    async def ocr(
        self,
        *,
        region: tuple[float, float, float, float] | None = None,
        full_page: bool = False,
        lang: str | None = None,
        image_bytes: bytes | None = None,
    ) -> list[OCRRegion]:
        """OCR and return typed :class:`OCRRegion` models."""
        self._ensure_open()
        if image_bytes is None:
            image_bytes = await self.screenshot(full_page=full_page)
        ocr_regions = await self._vision.ocr.ocr_image(
            image_bytes, region=region, lang=lang
        )
        self._last_vision = VisionResult(ocr_regions=ocr_regions, engine="tesseract")
        return ocr_regions

    async def ocr_element(
        self,
        target: int | Element | str,
        *,
        lang: str | None = None,
    ) -> list[OCRRegion]:
        """Screenshot a single element and OCR it (canvas/img friendly)."""
        self._ensure_open()
        locator = await self._resolve_locator(target)
        try:
            image_bytes = await locator.screenshot(type="png")
        except Exception as exc:
            raise ElementNotFoundError(
                f"ocr_element screenshot failed for {target!r}: {exc}"
            ) from exc
        return await self.ocr(image_bytes=image_bytes, lang=lang)

    async def ocr_text(
        self,
        *,
        region: tuple[float, float, float, float] | None = None,
        full_page: bool = False,
        lang: str | None = None,
        image_bytes: bytes | None = None,
        separator: str = " ",
    ) -> str:
        """Convenience: joined plain text from OCR regions."""
        regions = await self.ocr(
            region=region,
            full_page=full_page,
            lang=lang,
            image_bytes=image_bytes,
        )
        return self._vision.ocr.join_text(regions, separator=separator)

    # --- network intelligence (M5) ---

    def network_requests(
        self,
        *,
        filter: str | None = None,  # noqa: A002
        method: str | None = None,
        status: int | None = None,
        graphql_only: bool = False,
        failed_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Return captured network request summaries.

        ``filter`` is a substring, glob (``*/api/*``), or ``re:`` regex.
        """
        return self._network.network_requests(
            filter=filter,
            method=method,
            status=status,
            graphql_only=graphql_only,
            failed_only=failed_only,
        )

    def list_network_requests(
        self,
        *,
        filter: str | None = None,  # noqa: A002
        method: str | None = None,
        status: int | None = None,
        graphql_only: bool = False,
        failed_only: bool = False,
    ) -> list[NetworkRequest]:
        """Full :class:`NetworkRequest` models (includes bodies when captured)."""
        return self._network.list_requests(
            filter=filter,
            method=method,
            status=status,
            graphql_only=graphql_only,
            failed_only=failed_only,
        )

    async def wait_for_api(
        self,
        url_pattern: str,
        *,
        timeout_ms: int = 30_000,
        method: str | None = None,
        status: int | None = None,
    ) -> NetworkRequest:
        """Block until a matching XHR/fetch/API response is observed."""
        self._ensure_open()
        await self._ensure_network()
        return await self._network.wait_for_api(
            url_pattern,
            timeout_ms=timeout_ms,
            method=method,
            status=status,
        )

    def clear_network_log(self) -> None:
        """Clear captured requests for this page."""
        self._network.clear()

    async def route(
        self,
        url_pattern: str,
        handler: Callable[[Any], Any] | None = None,
        *,
        fulfill_json: Any | None = None,
        status: int = 200,
    ) -> None:
        """
        Intercept requests matching ``url_pattern`` (Playwright glob).

        Provide either a custom ``handler(route)`` or ``fulfill_json`` for a
        static JSON response (handy for tests and offline agents).
        """
        self._ensure_open()
        await self._ensure_network()

        if handler is not None:
            await self._page.route(url_pattern, handler)
            return

        if fulfill_json is not None:
            import json as _json

            body = _json.dumps(fulfill_json)

            async def _fulfill(route: Any) -> None:
                await route.fulfill(
                    status=status,
                    content_type="application/json",
                    body=body,
                )

            await self._page.route(url_pattern, _fulfill)
            return

        raise ValueError("route() requires handler= or fulfill_json=")

    async def unroute(self, url_pattern: str) -> None:
        self._ensure_open()
        await self._page.unroute(url_pattern)

    async def wait_for_network_idle(self, *, timeout_ms: float | None = None) -> None:
        """Wait until Playwright reports networkidle."""
        self._ensure_open()
        kwargs: dict[str, Any] = {}
        if timeout_ms is not None:
            kwargs["timeout"] = timeout_ms
        await self._page.wait_for_load_state("networkidle", **kwargs)

    # --- memory / planning (M7) ---

    async def context(
        self,
        *,
        max_tokens: int = 1000,
        goal: str | None = None,
        refresh: bool = True,
        include_memory: bool = True,
    ) -> dict[str, Any]:
        """
        LLM-oriented compressed page context.

        Ranks interactive elements and fits them into an approximate token budget.
        """
        if refresh or self._last_snapshot is None:
            await self.snapshot()
        assert self._last_snapshot is not None
        mem = self._memory.memory_summary() if include_memory else None
        return self._context_builder.build(
            self._last_snapshot,
            max_tokens=max_tokens,
            goal=goal,
            memory=mem,
        )

    async def plan(
        self,
        goal: str,
        *,
        refresh: bool = True,
        structured: bool = False,
    ) -> list[str] | dict[str, Any]:
        """Rule-based plan / action suggestions for ``goal``."""
        if refresh or self._last_snapshot is None:
            await self.snapshot()
        assert self._last_snapshot is not None
        self._memory.set("current_goal", goal)
        if structured:
            return self._planner.plan_structured(self._last_snapshot, goal)
        return self._planner.plan(self._last_snapshot, goal)

    def memory_summary(self) -> dict[str, Any]:
        return self._memory.memory_summary()

    async def detect_ui(
        self,
        *,
        full_page: bool = False,
        image_bytes: bytes | None = None,
    ) -> list[VisionDetection]:
        """
        Optional UI detection hook over a screenshot.

        Default engine is a lightweight heuristic (not a trained detector).
        """
        self._ensure_open()
        if image_bytes is None:
            image_bytes = await self.screenshot(full_page=full_page)
        detections = await self._vision.detector.detect(image_bytes)
        prev = self._last_vision
        self._last_vision = VisionResult(
            ocr_regions=list(prev.ocr_regions) if prev else [],
            detections=detections,
            engine="heuristic" if not prev else f"{prev.engine}+heuristic",
        )
        return detections

    async def analyze_vision(
        self,
        *,
        region: tuple[float, float, float, float] | None = None,
        full_page: bool = False,
        run_ocr: bool = True,
        run_detect: bool = False,
        lang: str | None = None,
        image_bytes: bytes | None = None,
    ) -> VisionResult:
        """Combined OCR (+ optional UI detection) pass."""
        self._ensure_open()
        if image_bytes is None:
            image_bytes = await self.screenshot(full_page=full_page)
        result = await self._vision.analyze(
            image_bytes,
            region=region,
            run_ocr=run_ocr,
            run_detect=run_detect,
            lang=lang,
        )
        self._last_vision = result
        return result

    def as_agent(
        self,
        *,
        detail: str = "normal",
        max_tokens: int = 2000,
        observe_after_action: bool = True,
        auto_settle: bool = True,
        auto_dismiss_overlays: bool = True,
        settle_budget_ms: float = 8_000,
        recover_stale: bool = True,
    ) -> Any:
        """
        Return an :class:`~agent_browser.agent.AgentSession` bound to this page.

        Preferred entrypoint for LLM tool loops (compact observations + ActionResult).
        """
        from agent_browser.agent.session import AgentSession

        return AgentSession(
            self,
            default_detail=detail,
            max_tokens=max_tokens,
            observe_after_action=observe_after_action,
            auto_settle=auto_settle,
            auto_dismiss_overlays=auto_dismiss_overlays,
            settle_budget_ms=settle_budget_ms,
            recover_stale=recover_stale,
        )

    async def observe(
        self,
        *,
        detail: str = "normal",
        max_tokens: int = 2000,
        include_diff: bool = True,
    ) -> Any:
        """Shortcut: compact LLM observation of the current page."""
        agent = self.as_agent(detail=detail, max_tokens=max_tokens)
        return await agent.observe(include_diff=include_diff)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._element_registry.clear()
        self._semantic.reset()
        try:
            await self._mutation.detach()
        except Exception:
            pass
        try:
            await self._events.close()
        except Exception:
            pass
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
        # Keep last_snapshot for navigation diffing? Clear so next snapshot is baseline.
        self._last_snapshot = None
        self._last_diff = None

    def _on_frame_navigated(self, frame: Any) -> None:
        # Only top-level frame; emission also done in goto/set_content for clarity
        try:
            if frame == self._page.main_frame:
                pass
        except Exception:
            pass

    async def _handle_mutation(self, payload: dict[str, Any]) -> None:
        await self._events.emit(self._mutation.mutation_event(payload))
        if self._auto_snapshot_on_mutation and not self._closed:
            try:
                await self.snapshot(emit_events=True)
            except Exception as exc:
                await self._events.emit(
                    BrowserEvent.make(EventType.ERROR, where="mutation_snapshot", error=str(exc))
                )

    async def _reattach_mutation_observer(self) -> None:
        # After navigation the observer is gone; re-inject script.
        # Binding remains on the page context.
        try:
            await self._page.evaluate(
                "() => { if (window.__agentBrowserMO) { window.__agentBrowserMO.disconnect(); delete window.__agentBrowserMO; } }"
            )
            await self._page.evaluate(
                # reuse monitor JS via attach path
                """
                (debounceMs) => {
                  let timer = null;
                  let batch = { childList: 0, attributes: 0, characterData: 0 };
                  const flush = () => {
                    timer = null;
                    const payload = {
                      childList: batch.childList,
                      attributes: batch.attributes,
                      characterData: batch.characterData,
                      ts: Date.now(),
                    };
                    batch = { childList: 0, attributes: 0, characterData: 0 };
                    if (window.__agentBrowserNotify) {
                      window.__agentBrowserNotify(payload);
                    }
                  };
                  const mo = new MutationObserver((mutations) => {
                    for (const m of mutations) {
                      if (m.type === 'childList') batch.childList += 1;
                      else if (m.type === 'attributes') {
                        if (m.attributeName === 'data-agent-id') continue;
                        batch.attributes += 1;
                      } else if (m.type === 'characterData') batch.characterData += 1;
                    }
                    if (batch.childList || batch.attributes || batch.characterData) {
                      if (timer) clearTimeout(timer);
                      timer = setTimeout(flush, debounceMs);
                    }
                  });
                  const root = document.documentElement || document.body;
                  if (root) {
                    mo.observe(root, {
                      childList: true,
                      subtree: true,
                      attributes: true,
                      characterData: true,
                    });
                  }
                  window.__agentBrowserMO = mo;
                  return true;
                }
                """,
                self._mutation.debounce_ms,
            )
            self._mutation._attached = True  # noqa: SLF001
        except Exception:
            self._watch_enabled = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Page is closed")

    async def _human_move_to_locator(self, locator: Any) -> None:
        """Move mouse along a humanized path toward the locator's box."""
        try:
            box = await locator.bounding_box()
        except Exception:
            box = None
        if not box:
            return
        end = self._humanize.target_point_from_box(
            box["x"], box["y"], box["width"], box["height"]
        )
        path = self._humanize.mouse_path(self._mouse_pos, end)
        for pt in path:
            await self._page.mouse.move(pt.x, pt.y)
            if self._humanize.enabled:
                await asyncio.sleep(random.uniform(0.005, 0.015))
        self._mouse_pos = end

    @staticmethod
    def _target_meta(target: int | Element | str) -> Any:
        if isinstance(target, Element):
            return {"id": target.id, "role": target.role, "text": target.text}
        if isinstance(target, int):
            return {"id": target}
        return {"selector": target}

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
