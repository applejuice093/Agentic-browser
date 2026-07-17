"""
AgentSession — the primary LLM-facing control loop.

Compact Observation + ActionResult every step, with settle, overlay dismiss,
stale-ref recovery, and tool dispatch.
"""

from __future__ import annotations

import time
from typing import Any

from agent_browser.agent.overlays import dismiss_overlays
from agent_browser.agent.settle import settle_page
from agent_browser.agent.wait import smart_wait
from agent_browser.exceptions import (
    AgentBrowserError,
    ElementNotFoundError,
    NavigationError,
    NetworkTimeoutError,
    SnapshotError,
    TimeoutError as AgentTimeout,
)
from agent_browser.models.diff import Diff
from agent_browser.models.observation import (
    ActionResult,
    DetailLevel,
    ErrorCode,
    Observation,
    WaitKind,
)
from agent_browser.observation.compact import build_observation
from agent_browser.page import Page


def _map_error(exc: BaseException) -> tuple[ErrorCode, str]:
    msg = str(exc)
    if isinstance(exc, ElementNotFoundError):
        low = msg.lower()
        if "stale" in low:
            return ErrorCode.ELEMENT_STALE, msg
        return ErrorCode.ELEMENT_NOT_FOUND, msg
    if isinstance(exc, NetworkTimeoutError):
        return ErrorCode.NETWORK_TIMEOUT, msg
    if isinstance(exc, AgentTimeout):
        return ErrorCode.TIMEOUT, msg
    if isinstance(exc, NavigationError):
        return ErrorCode.NAVIGATION_FAILED, msg
    if isinstance(exc, SnapshotError):
        return ErrorCode.SNAPSHOT_FAILED, msg
    if isinstance(exc, AgentBrowserError):
        if "closed" in msg.lower():
            return ErrorCode.PAGE_CLOSED, msg
        return ErrorCode.UNKNOWN, msg
    if "closed" in msg.lower():
        return ErrorCode.PAGE_CLOSED, msg
    if "timeout" in msg.lower():
        return ErrorCode.TIMEOUT, msg
    return ErrorCode.UNKNOWN, msg


class AgentSession:
    """
    LLM-optimized controller over :class:`Page`.

    Example::

        agent = await browser.open_agent(url)
        obs = await agent.observe()
        result = await agent.click(ref)
    """

    def __init__(
        self,
        page: Page,
        *,
        default_detail: DetailLevel | str = DetailLevel.NORMAL,
        max_tokens: int = 2000,
        observe_after_action: bool = True,
        auto_settle: bool = True,
        auto_dismiss_overlays: bool = True,
        settle_budget_ms: float = 8_000,
        recover_stale: bool = True,
    ) -> None:
        self.page = page
        self.default_detail = (
            DetailLevel(default_detail) if isinstance(default_detail, str) else default_detail
        )
        self.max_tokens = max_tokens
        self.observe_after_action = observe_after_action
        self.auto_settle = auto_settle
        self.auto_dismiss_overlays = auto_dismiss_overlays
        self.settle_budget_ms = settle_budget_ms
        self.recover_stale = recover_stale
        self.step = 0
        self._last_obs: Observation | None = None
        self._settled_once = False
        self._last_settle: dict[str, Any] = {}

    @property
    def last_observation(self) -> Observation | None:
        return self._last_obs

    def _detail(self, detail: DetailLevel | str | None) -> DetailLevel:
        if detail is None:
            return self.default_detail
        return DetailLevel(detail) if isinstance(detail, str) else detail

    async def prepare(
        self,
        *,
        budget_ms: float | None = None,
        scroll_probe: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Settle page + dismiss overlays. Called automatically on first observe
        after navigation when ``auto_settle`` is True.
        """
        if self._settled_once and not force:
            return self._last_settle
        stats = await settle_page(
            self.page,
            budget_ms=budget_ms or self.settle_budget_ms,
            dismiss_overlays=self.auto_dismiss_overlays,
            scroll_probe=scroll_probe,
        )
        self._last_settle = stats
        self._settled_once = True
        return stats

    async def dismiss_overlays(self) -> dict[str, Any]:
        return await dismiss_overlays(self.page)

    async def observe(
        self,
        *,
        detail: DetailLevel | str | None = None,
        max_tokens: int | None = None,
        include_diff: bool = True,
        resync: bool = False,
        note: str | None = None,
        prepare: bool | None = None,
        scroll_probe: bool = False,
    ) -> Observation:
        """Capture compact observation (optional settle/dismiss first)."""
        do_prep = self.auto_settle if prepare is None else prepare
        meta: dict[str, Any] = {}
        if do_prep:
            settle = await self.prepare(scroll_probe=scroll_probe, force=resync)
            meta["settle"] = {
                "elapsed_ms": settle.get("elapsed_ms"),
                "steps": settle.get("steps"),
            }
            if settle.get("overlays"):
                meta["overlays"] = {
                    "clicked": settle["overlays"].get("clicked"),
                    "hidden_nodes": settle["overlays"].get("hidden_nodes"),
                }

        self.step += 1
        d = self._detail(detail)
        snap = await self.page.snapshot(emit_events=False)
        diff: Diff | None = self.page.last_diff if include_diff else None
        net = self.page.list_network_requests()
        recent = net[-12:]
        obs = build_observation(
            snap,
            detail=d,
            diff=diff if include_diff else None,
            network=recent,
            max_tokens=max_tokens or self.max_tokens,
            include_boxes=(d == DetailLevel.FULL),
            step=self.step,
            note=note or ("resync" if resync else None),
            meta=meta,
        )
        self._last_obs = obs
        return obs

    async def resync(
        self,
        *,
        detail: DetailLevel | str | None = None,
        max_tokens: int | None = None,
    ) -> Observation:
        """Full recovery: dismiss overlays, optional scroll, fresh observation."""
        self._settled_once = False
        await self.prepare(force=True, scroll_probe=True)
        return await self.observe(
            detail=detail,
            max_tokens=max_tokens,
            include_diff=False,
            resync=True,
            prepare=False,
            note="resync",
        )

    async def navigate(
        self,
        url: str,
        *,
        detail: DetailLevel | str | None = None,
        observe: bool | None = None,
        settle: bool = True,
    ) -> ActionResult:
        t0 = time.perf_counter()
        url_before = self.page.url
        do_obs = self.observe_after_action if observe is None else observe
        self._settled_once = False
        try:
            await self.page.goto(url)
            if settle:
                await self.prepare(force=True, scroll_probe=True)
            elapsed = (time.perf_counter() - t0) * 1000
            obs = (
                await self.observe(detail=detail, prepare=False)
                if do_obs
                else None
            )
            return ActionResult(
                ok=True,
                action="navigate",
                elapsed_ms=elapsed,
                navigated=self.page.url != url_before,
                url_before=url_before,
                url_after=self.page.url,
                observation=obs,
                extra={"settle": self._last_settle},
            )
        except Exception as exc:
            code, msg = _map_error(exc)
            return ActionResult(
                ok=False,
                action="navigate",
                error_code=code,
                error_message=msg,
                elapsed_ms=(time.perf_counter() - t0) * 1000,
                url_before=url_before,
                url_after=self.page.url,
            )

    async def click(
        self,
        ref: int,
        *,
        observe: bool | None = None,
        detail: DetailLevel | str | None = None,
        text_hint: str | None = None,
    ) -> ActionResult:
        return await self._act(
            "click",
            ref,
            observe=observe,
            detail=detail,
            text_hint=text_hint,
        )

    async def type(
        self,
        ref: int,
        text: str,
        *,
        clear: bool = True,
        submit: bool = False,
        observe: bool | None = None,
        detail: DetailLevel | str | None = None,
        text_hint: str | None = None,
    ) -> ActionResult:
        t0 = time.perf_counter()
        url_before = self.page.url
        do_obs = self.observe_after_action if observe is None else observe
        target = ref
        try:
            if not self.page.last_snapshot:
                await self.page.snapshot(emit_events=False)

            async def _do() -> None:
                nonlocal target
                if clear:
                    await self.page.fill(target, text)
                else:
                    await self.page.type(target, text)
                if submit:
                    await self.page.press(target, "Enter")

            try:
                await _do()
            except ElementNotFoundError:
                if not self.recover_stale:
                    raise
                await self.resync(detail=detail)
                if text_hint:
                    matches = await self.find(text=text_hint)
                    if matches:
                        target = int(matches[0]["ref"])
                await _do()

            try:
                await self.page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            elapsed = (time.perf_counter() - t0) * 1000
            navigated = self.page.url != url_before
            if navigated:
                self._settled_once = False
            obs = (
                await self.observe(detail=detail, prepare=navigated)
                if do_obs
                else None
            )
            return ActionResult(
                ok=True,
                action="type",
                elapsed_ms=elapsed,
                target_ref=target,
                navigated=navigated,
                url_before=url_before,
                url_after=self.page.url,
                observation=obs,
                extra={"length": len(text), "submit": submit},
            )
        except Exception as exc:
            code, msg = _map_error(exc)
            if code == ErrorCode.ELEMENT_NOT_FOUND and self.recover_stale:
                code = ErrorCode.ELEMENT_STALE
            return ActionResult(
                ok=False,
                action="type",
                error_code=code,
                error_message=msg,
                elapsed_ms=(time.perf_counter() - t0) * 1000,
                target_ref=target,
                url_before=url_before,
                url_after=self.page.url,
            )

    async def fill(
        self,
        ref: int,
        text: str,
        *,
        observe: bool | None = None,
        detail: DetailLevel | str | None = None,
    ) -> ActionResult:
        return await self.type(ref, text, clear=True, observe=observe, detail=detail)

    async def _act(
        self,
        action: str,
        ref: int,
        *,
        observe: bool | None = None,
        detail: DetailLevel | str | None = None,
        text_hint: str | None = None,
    ) -> ActionResult:
        t0 = time.perf_counter()
        url_before = self.page.url
        do_obs = self.observe_after_action if observe is None else observe
        target = ref
        try:
            if not self.page.last_snapshot:
                await self.page.snapshot(emit_events=False)

            async def _do() -> None:
                nonlocal target
                if action == "click":
                    # scroll into view for reliability
                    try:
                        loc = self.page.playwright_page.locator(
                            f'[data-agent-id="{target}"]'
                        )
                        if await loc.count() > 0:
                            await loc.first.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass
                    await self.page.click(target)
                else:
                    raise ValueError(f"unsupported action {action}")

            try:
                await _do()
            except ElementNotFoundError:
                if not self.recover_stale:
                    raise
                await self.resync(detail=detail)
                if text_hint:
                    matches = await self.find(text=text_hint)
                    if matches:
                        target = int(matches[0]["ref"])
                    else:
                        raise
                else:
                    # try same ref after resync stamp
                    pass
                await _do()

            try:
                await self.page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            elapsed = (time.perf_counter() - t0) * 1000
            navigated = self.page.url != url_before
            if navigated:
                self._settled_once = False
            obs = (
                await self.observe(detail=detail, prepare=navigated)
                if do_obs
                else None
            )
            return ActionResult(
                ok=True,
                action=action,
                elapsed_ms=elapsed,
                target_ref=target,
                navigated=navigated,
                url_before=url_before,
                url_after=self.page.url,
                observation=obs,
            )
        except Exception as exc:
            code, msg = _map_error(exc)
            if code == ErrorCode.ELEMENT_NOT_FOUND and self.recover_stale:
                code = ErrorCode.ELEMENT_STALE
            return ActionResult(
                ok=False,
                action=action,
                error_code=code,
                error_message=msg,
                elapsed_ms=(time.perf_counter() - t0) * 1000,
                target_ref=target,
                url_before=url_before,
                url_after=self.page.url,
            )

    async def wait(
        self,
        kind: WaitKind = "timeout",
        *,
        value: str | float | None = None,
        timeout_ms: float = 15_000,
        observe: bool = False,
        detail: DetailLevel | str | None = None,
    ) -> ActionResult:
        t0 = time.perf_counter()
        result = await smart_wait(self.page, kind, value=value, timeout_ms=timeout_ms)
        obs = await self.observe(detail=detail) if observe and result.get("ok") else None
        return ActionResult(
            ok=bool(result.get("ok")),
            action=f"wait:{kind}",
            error_code=ErrorCode(result.get("error_code", ErrorCode.OK.value)),
            error_message=result.get("error_message"),
            elapsed_ms=result.get("elapsed_ms") or (time.perf_counter() - t0) * 1000,
            observation=obs,
            url_after=self.page.url,
        )

    async def find(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        text: str | None = None,
        exact: bool = False,
    ) -> list[dict[str, Any]]:
        """Return compact ref dicts matching criteria."""
        els: list[Any] = []
        if role:
            els = await self.page.get_all_by_role(
                role, name=name if name else None, exact=exact
            )
        elif name:
            els = await self.page.get_all_by_label(name, exact=exact)
        elif text:
            el = await self.page.get_by_text(text, exact=exact)
            els = [el] if el else []
        if text and els:
            t = text.lower()
            if exact:
                els = [
                    e
                    for e in els
                    if e
                    and (
                        (e.text or "").strip().lower() == t
                        or (e.name or "").strip().lower() == t
                    )
                ]
            else:
                els = [
                    e
                    for e in els
                    if e and (t in (e.text or "").lower() or t in (e.name or "").lower())
                ]
        return [
            {
                "ref": e.id,
                "role": e.role,
                "name": e.name,
                "text": (e.text or "")[:80],
                "tag": e.type,
            }
            for e in els
            if e is not None
        ]

    async def network(
        self,
        *,
        filter: str | None = None,  # noqa: A002
        graphql_only: bool = False,
    ) -> list[dict[str, Any]]:
        return self.page.network_requests(filter=filter, graphql_only=graphql_only)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Dispatch a tool by name (OpenAI/MCP-style)."""
        args = arguments or {}
        if name == "browser_navigate":
            r = await self.navigate(args["url"], detail=args.get("detail"))
            return r.to_llm_dict()
        if name == "browser_observe":
            o = await self.observe(
                detail=args.get("detail"),
                max_tokens=args.get("max_tokens"),
                include_diff=args.get("include_diff", True),
            )
            return o.to_llm_dict()
        if name == "browser_click":
            r = await self.click(
                int(args["ref"]),
                observe=args.get("observe", True),
                text_hint=args.get("text_hint"),
            )
            return r.to_llm_dict()
        if name == "browser_type":
            r = await self.type(
                int(args["ref"]),
                args["text"],
                clear=args.get("clear", True),
                submit=args.get("submit", False),
                observe=args.get("observe", True),
            )
            return r.to_llm_dict()
        if name == "browser_wait":
            r = await self.wait(
                args.get("kind", "timeout"),
                value=args.get("value"),
                timeout_ms=float(args.get("timeout_ms", 15_000)),
            )
            return r.to_llm_dict()
        if name == "browser_find":
            return {
                "ok": True,
                "matches": await self.find(
                    role=args.get("role"),
                    name=args.get("name"),
                    text=args.get("text"),
                    exact=args.get("exact", False),
                ),
            }
        if name == "browser_network":
            return {
                "ok": True,
                "requests": await self.network(
                    filter=args.get("filter"),
                    graphql_only=args.get("graphql_only", False),
                ),
            }
        if name == "browser_resync":
            o = await self.resync(detail=args.get("detail"))
            return o.to_llm_dict()
        if name == "browser_prepare":
            stats = await self.prepare(force=True, scroll_probe=True)
            return {"ok": True, **stats}
        return {
            "ok": False,
            "error_code": ErrorCode.INVALID_ARGS.value,
            "error_message": f"unknown tool: {name}",
        }
