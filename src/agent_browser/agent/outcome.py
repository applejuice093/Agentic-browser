"""
Post-action outcome verification.

BrowserGym returns last action errors; agent eval research emphasizes verifying
task progress (URL change, DOM assertion), not only exception-free execution.
"""

from __future__ import annotations

import re
import time
from typing import Any

from pydantic import BaseModel, Field

from agent_browser.models.observation import ErrorCode


class OutcomeExpectation(BaseModel):
    """Optional success criteria for an action."""

    url_contains: str | None = None
    url_regex: str | None = None
    url_changed: bool | None = None
    text_contains: str | None = None
    selector: str | None = None
    timeout_ms: float = 3_000
    # if True, navigated must be true
    require_navigation: bool = False


class OutcomeReport(BaseModel):
    verified: bool
    error_code: ErrorCode = ErrorCode.OK
    message: str = ""
    url_before: str = ""
    url_after: str = ""
    checks: dict[str, Any] = Field(default_factory=dict)


async def verify_outcome(
    page: Any,
    *,
    url_before: str,
    expectation: OutcomeExpectation | None,
    action_ok_so_far: bool = True,
) -> OutcomeReport:
    """
    Verify page state against expectation after an action that did not throw.

    If no expectation, success = action_ok_so_far only (legacy). Prefer
    explicit expectations for agent tasks.
    """
    url_after = page.url
    if not action_ok_so_far:
        return OutcomeReport(
            verified=False,
            error_code=ErrorCode.UNKNOWN,
            message="action raised before verification",
            url_before=url_before,
            url_after=url_after,
        )

    if expectation is None:
        return OutcomeReport(
            verified=True,
            message="no expectation; exception-free only",
            url_before=url_before,
            url_after=url_after,
            checks={"mode": "exception_free"},
        )

    deadline = time.monotonic() + expectation.timeout_ms / 1000.0
    checks: dict[str, Any] = {}
    last_fail = "expectation_not_met"

    while time.monotonic() < deadline:
        url_after = page.url
        ok = True

        if expectation.require_navigation or expectation.url_changed:
            changed = url_after != url_before
            checks["url_changed"] = changed
            if not changed:
                ok = False
                last_fail = "expected_navigation"

        if expectation.url_contains:
            hit = expectation.url_contains in url_after
            checks["url_contains"] = hit
            if not hit:
                ok = False
                last_fail = f"url_missing:{expectation.url_contains}"

        if expectation.url_regex:
            hit = bool(re.search(expectation.url_regex, url_after))
            checks["url_regex"] = hit
            if not hit:
                ok = False
                last_fail = f"url_regex_fail:{expectation.url_regex}"

        if expectation.text_contains:
            try:
                body = await page.evaluate(
                    "() => ((document.body&&document.body.innerText)||'').slice(0,8000)"
                )
                hit = expectation.text_contains.lower() in (body or "").lower()
            except Exception:
                hit = False
            checks["text_contains"] = hit
            if not hit:
                ok = False
                last_fail = f"text_missing:{expectation.text_contains}"

        if expectation.selector:
            try:
                await page.wait_for_selector(
                    expectation.selector, state="visible", timeout_ms=200
                )
                checks["selector"] = True
            except Exception:
                checks["selector"] = False
                ok = False
                last_fail = f"selector_missing:{expectation.selector}"

        if ok:
            return OutcomeReport(
                verified=True,
                message="outcome verified",
                url_before=url_before,
                url_after=url_after,
                checks=checks,
            )
        await _sleep(0.08)

    return OutcomeReport(
        verified=False,
        error_code=ErrorCode.UNKNOWN,
        message=last_fail,
        url_before=url_before,
        url_after=page.url,
        checks=checks,
    )


async def _sleep(s: float) -> None:
    import asyncio

    await asyncio.sleep(s)


def expectation_for_intent(
    intent: str | None,
    *,
    text_hint: str | None = None,
) -> OutcomeExpectation | None:
    """
    Map common natural intents to post-conditions (skill-agnostic heuristics).
    """
    blob = f"{intent or ''} {text_hint or ''}".lower()
    if not blob.strip():
        return None
    # GitHub-ish / generic nav tabs
    if re.search(r"\bissues?\b", blob) and "pull" not in blob:
        return OutcomeExpectation(
            url_contains="/issues",
            require_navigation=True,
            timeout_ms=4_000,
        )
    if re.search(r"\bpull requests?\b|\bprs?\b", blob):
        return OutcomeExpectation(
            url_contains="/pulls",
            require_navigation=True,
            timeout_ms=4_000,
        )
    if re.search(r"\bactions\b", blob) and "react" not in blob:
        return OutcomeExpectation(
            url_contains="/actions", require_navigation=True, timeout_ms=4_000
        )
    if re.search(r"\bwiki\b", blob):
        return OutcomeExpectation(
            url_contains="/wiki", require_navigation=True, timeout_ms=4_000
        )
    if re.search(r"\bsecurity\b", blob):
        return OutcomeExpectation(
            url_contains="/security", require_navigation=True, timeout_ms=4_000
        )
    if re.search(r"\bprojects?\b", blob):
        return OutcomeExpectation(
            url_contains="/projects", require_navigation=True, timeout_ms=4_000
        )
    if re.search(r"\bcode\b|repository files", blob):
        # often already on code — soft check
        return OutcomeExpectation(url_changed=False, timeout_ms=500)
    if re.search(r"\blog ?in\b|\bsign ?in\b", blob):
        return OutcomeExpectation(
            url_regex=r"login|signin|session",
            require_navigation=True,
            timeout_ms=4_000,
        )
    return None
