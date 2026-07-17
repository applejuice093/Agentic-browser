"""
Overlay / consent / modal dismissal for agent browsing.

Complex marketing sites (Rockstar, news, EU CMP) inject cookie and privacy
UI that pollutes observations. This module detects and clears common patterns
so the LLM sees the real product page.
"""

from __future__ import annotations

import re
from typing import Any

# Button/link text patterns (case-insensitive)
_ACCEPT_PATTERNS = [
    r"^accept all$",
    r"^accept$",
    r"^accept cookies$",
    r"^allow all$",
    r"^allow all cookies$",
    r"^i agree$",
    r"^agree$",
    r"^agree and close$",
    r"^got it$",
    r"^ok$",
    r"^okay$",
    r"^continue$",
    r"^confirm$",
    r"^save and close$",
    r"^save preferences$",
    r"^yes,? i.?m \d+",
    r"^enter$",
    r"^close$",
    r"^dismiss$",
    r"^no thanks$",
    r"^reject all$",  # sometimes cleaner than accept for observation
    r"^necessary only$",
    r"^essential only$",
]

_OVERLAY_ROOT_SELECTORS = [
    "#onetrust-banner-sdk",
    "#onetrust-consent-sdk",
    ".onetrust-pc-dark-filter",
    "#CybotCookiebotDialog",
    ".cc-window",
    ".cookie-banner",
    "[id*='cookie'][role='dialog']",
    "[class*='cookie'][role='dialog']",
    "[id*='consent']",
    "[class*='Consent']",
    "[aria-label*='cookie' i]",
    "[aria-label*='privacy' i]",
    "[aria-modal='true']",
    "div[class*='modal'][class*='open']",
    "#privacy-pref",
    ".ot-sdk-container",
]

_CLICK_SELECTORS = [
    "#onetrust-accept-btn-handler",
    "#onetrust-reject-all-handler",
    "button#accept-recommended-btn-handler",
    ".cc-btn.cc-dismiss",
    ".cc-allow",
    "button[mode='primary']",
    "[data-testid*='accept' i]",
    "[data-testid*='cookie-accept' i]",
    "button[aria-label*='Accept' i]",
    "button[aria-label*='Close' i]",
]


def _matches_accept(text: str) -> bool:
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not t or len(t) > 80:
        return False
    return any(re.search(p, t, re.I) for p in _ACCEPT_PATTERNS)


async def dismiss_overlays(page: Any, *, max_passes: int = 3) -> dict[str, Any]:
    """
    Best-effort dismiss of cookie/consent/age overlays.

    ``page`` is an agent_browser.Page (has playwright_page, click, evaluate).
    Returns stats for tracing.
    """
    pw = page.playwright_page
    clicked: list[str] = []
    removed = 0

    for _ in range(max_passes):
        progressed = False

        # 1) Known vendor CSS buttons
        for sel in _CLICK_SELECTORS:
            try:
                loc = pw.locator(sel)
                n = await loc.count()
                if n == 0:
                    continue
                btn = loc.first
                if await btn.is_visible():
                    await btn.click(timeout=2000)
                    clicked.append(sel)
                    progressed = True
                    await pw.wait_for_timeout(300)
            except Exception:
                continue

        # 2) Role=button with accept-like names via Playwright get_by_role
        try:
            for label in (
                "Accept All",
                "Accept all",
                "Accept Cookies",
                "Allow all",
                "I Agree",
                "Agree",
                "Got it",
                "Close",
                "Reject All",
                "Save and Close",
            ):
                loc = pw.get_by_role("button", name=label, exact=False)
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.click(timeout=2000)
                    clicked.append(f"role:button:{label}")
                    progressed = True
                    await pw.wait_for_timeout(300)
                    break
        except Exception:
            pass

        # 3) Scan buttons/links in page for text patterns (JS)
        try:
            handle = await pw.evaluate(
                """(patterns) => {
                  const reList = patterns.map(p => new RegExp(p, 'i'));
                  const candidates = Array.from(
                    document.querySelectorAll('button, a, [role="button"], input[type="button"], input[type="submit"]')
                  );
                  for (const el of candidates) {
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
                    if (!t || t.length > 80) continue;
                    if (reList.some(re => re.test(t))) {
                      el.click();
                      return t;
                    }
                  }
                  return null;
                }""",
                _ACCEPT_PATTERNS,
            )
            if handle:
                clicked.append(f"js:{handle}")
                progressed = True
                await pw.wait_for_timeout(300)
        except Exception:
            pass

        # 4) Hide stubborn overlay roots (last resort — observation hygiene)
        try:
            n = await pw.evaluate(
                """(sels) => {
                  let n = 0;
                  for (const sel of sels) {
                    document.querySelectorAll(sel).forEach(el => {
                      const t = (el.innerText || '').toLowerCase();
                      if (
                        t.includes('cookie') ||
                        t.includes('consent') ||
                        t.includes('privacy preference') ||
                        el.id.toLowerCase().includes('onetrust') ||
                        (el.getAttribute('aria-modal') === 'true' && t.includes('privacy'))
                      ) {
                        el.style.setProperty('display', 'none', 'important');
                        el.setAttribute('data-agent-dismissed', '1');
                        n += 1;
                      }
                    });
                  }
                  // unlock scroll
                  document.documentElement.style.overflow = '';
                  document.body.style.overflow = '';
                  return n;
                }""",
                _OVERLAY_ROOT_SELECTORS,
            )
            if n:
                removed += int(n)
                progressed = True
        except Exception:
            pass

        if not progressed:
            break

    return {"clicked": clicked, "hidden_nodes": removed, "passes": max_passes}


_NOISE_HEADING_RE = re.compile(
    r"privacy|cookie|consent|preference center|manage consent|gdpr|subscribe|newsletter|sign up for",
    re.I,
)


def is_noise_text(text: str | None) -> bool:
    if not text:
        return False
    return bool(_NOISE_HEADING_RE.search(text))
