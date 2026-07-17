"""
AgentSession — the primary LLM-facing control loop.

Provides observe / act / wait with compact Observation + ActionResult every step.
"""

from __future__ import annotations

import time
from typing import Any

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
    Thin policy layer over :class:`Page` optimized for LLM tool loops.

    Example::

        agent = AgentSession(page)
        obs = await agent.observe()
        result = await agent.click(obs.interactive[0].ref)
        print(result.to_llm_dict())
    """

    def __init__(
        self,
        page: Page,
        *,
        default_detail: DetailLevel | str = DetailLevel.NORMAL,
        max_tokens: int = 2000,
        observe_after_action: bool = True,
    ) -> None:
        self.page = page
        self.default_detail = (
            DetailLevel(default_detail) if isinstance(default_detail, str) else default_detail
        )
        self.max_tokens = max_tokens
        self.observe_after_action = observe_after_action
        self.step = 0
        self._last_obs: Observation | None = None

    @property
    def last_observation(self) -> Observation | None:
        return self._last_obs

    def _detail(self, detail: DetailLevel | str | None) -> DetailLevel:
        if detail is None:
            return self.default_detail
        return DetailLevel(detail) if isinstance(detail, str) else detail

    async def observe(
        self,
        *,
        detail: DetailLevel | str | None = None,
        max_tokens: int | None = None,
        include_diff: bool = True,
        resync: bool = False,
        note: str | None = None,
    ) -> Observation:
        """Capture compact observation (and optional diff vs previous full snapshot)."""
        self.step += 1
        d = self._detail(detail)
        snap = await self.page.snapshot(emit_events=False)
        diff: Diff | None = self.page.last_diff if include_diff else None
        # last_diff is vs previous snapshot — good for step deltas
        net = self.page.list_network_requests()
        # Only recent network (last ~15s or last 12)
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
        )
        self._last_obs = obs
        return obs

    async def resync(
        self,
        *,
        detail: DetailLevel | str | None = None,
        max_tokens: int | None = None,
    ) -> Observation:
        """Force a fresh observation (agent lost track of refs)."""
        return await self.observe(
            detail=detail,
            max_tokens=max_tokens,
            include_diff=False,
            resync=True,
            note="resync",
        )

    async def navigate(
        self,
        url: str,
        *,
        detail: DetailLevel | str | None = None,
        observe: bool | None = None,
    ) -> ActionResult:
        t0 = time.perf_counter()
        url_before = self.page.url
        do_obs = self.observe_after_action if observe is None else observe
        try:
            await self.page.goto(url)
            elapsed = (time.perf_counter() - t0) * 1000
            obs = await self.observe(detail=detail) if do_obs else None
            return ActionResult(
                ok=True,
                action="navigate",
                elapsed_ms=elapsed,
                navigated=self.page.url != url_before,
                url_before=url_before,
                url_after=self.page.url,
                observation=obs,
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
    ) -> ActionResult:
        return await self._act("click", ref, observe=observe, detail=detail)

    async def type(
        self,
        ref: int,
        text: str,
        *,
        clear: bool = True,
        submit: bool = False,
        observe: bool | None = None,
        detail: DetailLevel | str | None = None,
    ) -> ActionResult:
        t0 = time.perf_counter()
        url_before = self.page.url
        do_obs = self.observe_after_action if observe is None else observe
        try:
            # Ensure snapshot ids exist
            if not self.page.last_snapshot:
                await self.page.snapshot(emit_events=False)
            if clear:
                await self.page.fill(ref, text)
            else:
                await self.page.type(ref, text)
            if submit:
                await self.page.press(ref, "Enter")
            elapsed = (time.perf_counter() - t0) * 1000
            navigated = self.page.url != url_before
            obs = await self.observe(detail=detail) if do_obs else None
            return ActionResult(
                ok=True,
                action="type",
                elapsed_ms=elapsed,
                target_ref=ref,
                navigated=navigated,
                url_before=url_before,
                url_after=self.page.url,
                observation=obs,
                extra={"length": len(text), "submit": submit},
            )
        except Exception as exc:
            code, msg = _map_error(exc)
            return ActionResult(
                ok=False,
                action="type",
                error_code=code,
                error_message=msg,
                elapsed_ms=(time.perf_counter() - t0) * 1000,
                target_ref=ref,
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
    ) -> ActionResult:
        t0 = time.perf_counter()
        url_before = self.page.url
        do_obs = self.observe_after_action if observe is None else observe
        try:
            if not self.page.last_snapshot:
                await self.page.snapshot(emit_events=False)
            if action == "click":
                await self.page.click(ref)
            else:
                raise ValueError(f"unsupported action {action}")
            # Brief settle for SPA navigation
            try:
                await self.page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            elapsed = (time.perf_counter() - t0) * 1000
            navigated = self.page.url != url_before
            obs = await self.observe(detail=detail) if do_obs else None
            return ActionResult(
                ok=True,
                action=action,
                elapsed_ms=elapsed,
                target_ref=ref,
                navigated=navigated,
                url_before=url_before,
                url_after=self.page.url,
                observation=obs,
            )
        except Exception as exc:
            code, msg = _map_error(exc)
            return ActionResult(
                ok=False,
                action=action,
                error_code=code,
                error_message=msg,
                elapsed_ms=(time.perf_counter() - t0) * 1000,
                target_ref=ref,
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
            r = await self.click(int(args["ref"]), observe=args.get("observe", True))
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
        return {
            "ok": False,
            "error_code": ErrorCode.INVALID_ARGS.value,
            "error_message": f"unknown tool: {name}",
        }
