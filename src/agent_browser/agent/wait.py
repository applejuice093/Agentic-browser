"""Smart wait helpers for agent action loops."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any, TYPE_CHECKING

from agent_browser.exceptions import NetworkTimeoutError, TimeoutError as AgentTimeout
from agent_browser.models.observation import ErrorCode, WaitKind

if TYPE_CHECKING:
    from agent_browser.page import Page


async def smart_wait(
    page: Page,
    kind: WaitKind = "timeout",
    *,
    value: str | float | None = None,
    timeout_ms: float = 15_000,
) -> dict[str, Any]:
    """
    Unified wait for agent tools.

    kind:
      - timeout: sleep ``value`` ms (or timeout_ms)
      - selector: CSS/text selector visible
      - url: substring or re: pattern on page.url
      - text: body innerText contains value
      - networkidle / load / domcontentloaded
      - api: wait_for_api(value)
    """
    t0 = time.perf_counter()
    try:
        if kind == "timeout":
            ms = float(value) if value is not None else timeout_ms
            await asyncio.sleep(max(0.0, ms) / 1000.0)
        elif kind in ("networkidle", "load", "domcontentloaded"):
            await page.wait_for_load_state(kind)  # type: ignore[arg-type]
        elif kind == "selector":
            if not value or not isinstance(value, str):
                raise AgentTimeout("selector wait requires value=selector string")
            await page.wait_for_selector(value, timeout_ms=timeout_ms)
        elif kind == "url":
            if not value or not isinstance(value, str):
                raise AgentTimeout("url wait requires value=pattern")
            deadline = time.monotonic() + timeout_ms / 1000.0
            pattern = value
            while time.monotonic() < deadline:
                url = page.url
                if pattern.startswith("re:"):
                    if re.search(pattern[3:], url):
                        break
                elif pattern in url:
                    break
                await asyncio.sleep(0.05)
            else:
                raise AgentTimeout(f"url wait timed out for {pattern!r} (last={page.url})")
        elif kind == "text":
            if not value or not isinstance(value, str):
                raise AgentTimeout("text wait requires value=substring")
            deadline = time.monotonic() + timeout_ms / 1000.0
            while time.monotonic() < deadline:
                body = await page.evaluate(
                    "() => (document.body && document.body.innerText) || ''"
                )
                if value in (body or ""):
                    break
                await asyncio.sleep(0.1)
            else:
                raise AgentTimeout(f"text wait timed out for {value!r}")
        elif kind == "api":
            if not value or not isinstance(value, str):
                raise AgentTimeout("api wait requires value=url pattern")
            await page.wait_for_api(value, timeout_ms=int(timeout_ms))
        else:
            raise AgentTimeout(f"unknown wait kind: {kind}")
        return {
            "ok": True,
            "error_code": ErrorCode.OK.value,
            "elapsed_ms": (time.perf_counter() - t0) * 1000,
            "kind": kind,
        }
    except NetworkTimeoutError as exc:
        return {
            "ok": False,
            "error_code": ErrorCode.NETWORK_TIMEOUT.value,
            "error_message": str(exc),
            "elapsed_ms": (time.perf_counter() - t0) * 1000,
            "kind": kind,
        }
    except Exception as exc:
        msg = str(exc)
        code = ErrorCode.TIMEOUT
        if "closed" in msg.lower():
            code = ErrorCode.PAGE_CLOSED
        return {
            "ok": False,
            "error_code": code.value,
            "error_message": msg,
            "elapsed_ms": (time.perf_counter() - t0) * 1000,
            "kind": kind,
        }
