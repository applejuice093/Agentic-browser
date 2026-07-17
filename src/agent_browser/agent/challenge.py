"""
Bot-wall / challenge / soft-block detection.

Research context: production web agents fail not only on reasoning but on
environment gates (CAPTCHA, JS challenges, login walls). Detecting these
explicitly (instead of returning empty "success" observations) is standard
in BrowserGym-style stacks (last action error + page state signals).

We do NOT bypass challenges — we classify and surface them to the LLM.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PageGate(str, Enum):
    """High-level environment gate for agent branching."""

    OPEN = "open"  # usable product content
    LOGIN_WALL = "login_wall"
    COOKIE_WALL = "cookie_wall"
    CAPTCHA = "captcha"
    JS_CHALLENGE = "js_challenge"
    RATE_LIMIT = "rate_limit"
    SOFT_BLOCK = "soft_block"
    ERROR_PAGE = "error_page"
    EMPTY = "empty"
    UNKNOWN = "unknown"


class ChallengeReport(BaseModel):
    gate: PageGate = PageGate.OPEN
    confidence: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    title: str = ""
    url: str = ""
    body_snippet: str = ""
    recoverable_hint: str | None = None

    @property
    def is_blocked(self) -> bool:
        return self.gate not in (PageGate.OPEN, PageGate.COOKIE_WALL, PageGate.UNKNOWN)

    @property
    def is_usable(self) -> bool:
        return self.gate in (PageGate.OPEN, PageGate.COOKIE_WALL)


_URL_PATTERNS: list[tuple[PageGate, re.Pattern[str], str]] = [
    (PageGate.JS_CHALLENGE, re.compile(r"js_challenge|jsc_orig|cf_chl|challenge-platform|cdn-cgi/challenge", re.I), "url_js_challenge"),
    (PageGate.CAPTCHA, re.compile(r"captcha|recaptcha|hcaptcha|turnstile", re.I), "url_captcha"),
    (PageGate.LOGIN_WALL, re.compile(r"/login|/signin|/sign-in|/auth/|/session/new", re.I), "url_login"),
    (PageGate.RATE_LIMIT, re.compile(r"rate.?limit|too.?many.?requests|429", re.I), "url_rate"),
]

_TITLE_BODY_PATTERNS: list[tuple[PageGate, re.Pattern[str], str, float]] = [
    (PageGate.JS_CHALLENGE, re.compile(r"verifying your browser|just a moment|checking your browser|please wait while we|enable javascript|attention required|please wait for verification", re.I), "verify_browser", 0.95),
    (PageGate.CAPTCHA, re.compile(r"captcha|i.?m not a robot|hcaptcha|recaptcha|cloudflare", re.I), "captcha_text", 0.9),
    (PageGate.LOGIN_WALL, re.compile(r"sign in to continue|log in to continue|create an account to|authentication required", re.I), "login_wall_text", 0.85),
    (PageGate.RATE_LIMIT, re.compile(r"too many requests|rate limit|slow down|429", re.I), "rate_text", 0.9),
    (PageGate.SOFT_BLOCK, re.compile(r"access denied|request blocked|unusual traffic|automated queries|bot detection", re.I), "soft_block_text", 0.85),
    (PageGate.ERROR_PAGE, re.compile(r"404|page not found|something went wrong|internal server error|502 bad gateway", re.I), "error_page_text", 0.7),
    (PageGate.COOKIE_WALL, re.compile(r"we use cookies|accept all cookies|cookie preferences|privacy preference center", re.I), "cookie_wall_text", 0.6),
]

_HINTS = {
    PageGate.JS_CHALLENGE: "Environment is serving a JS/bot challenge. Do not invent page content; report blocked and stop or ask user.",
    PageGate.CAPTCHA: "CAPTCHA present. Human solve or different session required; do not loop clicks.",
    PageGate.LOGIN_WALL: "Login required for this view. Use credentials tool if authorized, else stop.",
    PageGate.RATE_LIMIT: "Rate limited. Back off and retry later.",
    PageGate.SOFT_BLOCK: "Soft block / bot detection. Change approach or stop.",
    PageGate.ERROR_PAGE: "Error page. Check URL or go back.",
    PageGate.COOKIE_WALL: "Cookie consent UI may be covering content; run browser_prepare / dismiss overlays.",
    PageGate.EMPTY: "Page body is empty or near-empty after load.",
    PageGate.OPEN: None,
    PageGate.UNKNOWN: "Could not confidently classify page gate.",
}


def classify_page_text(
    *,
    url: str,
    title: str,
    body_text: str,
    html_snippet: str = "",
) -> ChallengeReport:
    """Classify gate from URL + title + body (no browser required)."""
    reasons: list[str] = []
    best_gate = PageGate.OPEN
    conf = 0.15
    blob = f"{title}\n{body_text}\n{html_snippet[:2000]}"

    for gate, pat, reason in _URL_PATTERNS:
        if pat.search(url or ""):
            reasons.append(reason)
            if conf < 0.95:
                best_gate, conf = gate, 0.95

    for gate, pat, reason, c in _TITLE_BODY_PATTERNS:
        if pat.search(blob):
            reasons.append(reason)
            if c >= conf:
                best_gate, conf = gate, c

    stripped = re.sub(r"\s+", " ", body_text or "").strip()
    if len(stripped) < 40 and best_gate == PageGate.OPEN:
        # challenge pages often tiny
        if re.search(r"wait|verif|challenge|javascript", stripped, re.I):
            best_gate, conf = PageGate.JS_CHALLENGE, max(conf, 0.8)
            reasons.append("tiny_body_with_verify_language")
        else:
            best_gate, conf = PageGate.EMPTY, max(conf, 0.55)
            reasons.append("near_empty_body")

    return ChallengeReport(
        gate=best_gate,
        confidence=conf,
        reasons=reasons,
        title=title or "",
        url=url or "",
        body_snippet=stripped[:240],
        recoverable_hint=_HINTS.get(best_gate),
    )


async def detect_challenge(page: Any) -> ChallengeReport:
    """Live detection against an agent_browser.Page."""
    try:
        url = page.url
        title = await page.title()
        body = await page.evaluate(
            """() => ((document.body && document.body.innerText) || '')
                .replace(/\\s+/g, ' ').trim().slice(0, 2500)"""
        )
        # quick DOM signals
        html_flags = await page.evaluate(
            """() => {
              const has = (sel) => !!document.querySelector(sel);
              return {
                recaptcha: has('iframe[src*="recaptcha"]') || has('.g-recaptcha'),
                hcaptcha: has('iframe[src*="hcaptcha"]') || has('.h-captcha'),
                turnstile: has('iframe[src*="challenges.cloudflare"]') || has('[name="cf-turnstile-response"]'),
                challenge_form: has('#challenge-form') || has('#cf-challenge-running'),
              };
            }"""
        )
    except Exception as exc:
        return ChallengeReport(
            gate=PageGate.UNKNOWN,
            confidence=0.3,
            reasons=[f"detect_error:{exc}"],
            recoverable_hint="Page probe failed; treat as unknown.",
        )

    report = classify_page_text(url=url, title=title, body_text=body or "")
    if html_flags.get("recaptcha") or html_flags.get("hcaptcha") or html_flags.get("turnstile"):
        report.gate = PageGate.CAPTCHA
        report.confidence = max(report.confidence, 0.95)
        report.reasons.append("dom_captcha_widget")
        report.recoverable_hint = _HINTS[PageGate.CAPTCHA]
    if html_flags.get("challenge_form"):
        report.gate = PageGate.JS_CHALLENGE
        report.confidence = max(report.confidence, 0.95)
        report.reasons.append("dom_cf_challenge_form")
        report.recoverable_hint = _HINTS[PageGate.JS_CHALLENGE]
    report.title = title or report.title
    report.url = url
    report.body_snippet = (body or "")[:240]
    return report
