"""Stale-ref recovery and action retry for agent sessions."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from agent_browser.exceptions import ElementNotFoundError
from agent_browser.models.observation import ErrorCode

T = TypeVar("T")


async def with_stale_recovery(
    *,
    resync: Callable[[], Awaitable[Any]],
    action: Callable[[], Awaitable[T]],
    resolve_ref: Callable[[], Awaitable[int | None]] | None = None,
    max_retries: int = 1,
) -> tuple[T | None, dict[str, Any]]:
    """
    Run ``action``; on element-not-found, resync and optionally re-resolve ref once.
    """
    meta: dict[str, Any] = {"retries": 0, "recovered": False}
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            result = await action()
            return result, meta
        except ElementNotFoundError as exc:
            last_exc = exc
            meta["retries"] = attempt + 1
            if attempt >= max_retries:
                break
            await resync()
            meta["recovered"] = True
            if resolve_ref is not None:
                new_ref = await resolve_ref()
                meta["new_ref"] = new_ref
                if new_ref is None:
                    break
        except Exception as exc:
            last_exc = exc
            break
    return None, {
        **meta,
        "error_code": ErrorCode.ELEMENT_STALE.value
        if last_exc and "not found" in str(last_exc).lower()
        else ErrorCode.UNKNOWN.value,
        "error_message": str(last_exc) if last_exc else "recovery failed",
    }
