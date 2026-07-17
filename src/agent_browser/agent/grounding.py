"""
Scoped element grounding for web agents.

Inspired by BrowserGym bids + dual grounding / accessibility-first research:
prefer navigational chrome and exact names over long content-body links
(commit messages, PR descriptions, etc. that false-match 'Issues').
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Iterable

from agent_browser.models.element import Element


class FindScope(str, Enum):
    """Where to search for an element."""

    ANY = "any"
    NAV = "nav"  # banner / navigation / menubar / tabs
    MAIN = "main"  # main content only
    FORM = "form"


# Regions that indicate chrome vs dense content
_NAV_ROLES = frozenset(
    {
        "navigation",
        "banner",
        "menubar",
        "menu",
        "menuitem",
        "tab",
        "tablist",
        "toolbar",
    }
)
_NAV_TAGS = frozenset({"nav", "header"})
_MAIN_ROLES = frozenset({"main", "article", "region"})
_MAIN_TAGS = frozenset({"main", "article"})

# href/path patterns for dense noise (GitHub commits, PR blobs)
_NOISE_HREF = re.compile(
    r"/commit/|/commits/|/pull/\d+|/issues/\d+#|/blob/|/tree/|/compare/|"
    r"githubusercontent|/actions/runs|/discussions/\d+",
    re.I,
)
_NOISE_CLASS = re.compile(
    r"commit|timeline|markdown-body|js-timeline|Box-row|react-issue|js-navigation-item",
    re.I,
)


def element_region_score(el: Element, scope: FindScope) -> float:
    """Higher = better match for scope."""
    role = (el.role or "").lower()
    tag = (el.type or "").lower()
    href = el.attributes.get("href") or ""
    cls = el.attributes.get("class") or ""
    pid = el.parent_id

    navish = role in _NAV_ROLES or tag in _NAV_TAGS
    mainish = role in _MAIN_ROLES or tag in _MAIN_TAGS
    formish = role == "form" or tag == "form" or role in ("textbox", "checkbox", "radio")

    # noise penalty
    noise = 0.0
    if _NOISE_HREF.search(href):
        noise += 3.0
    if _NOISE_CLASS.search(cls):
        noise += 1.5
    # long text is usually content, not nav label
    text_len = len((el.text or "").strip())
    if text_len > 80:
        noise += 2.0
    if text_len > 200:
        noise += 3.0

    if scope == FindScope.NAV:
        base = 5.0 if navish else (1.0 if not mainish else 0.2)
        # short labeled links/buttons preferred in nav
        if text_len and text_len <= 40:
            base += 1.5
        return base - noise
    if scope == FindScope.MAIN:
        base = 5.0 if mainish else (2.0 if not navish else 0.5)
        return base - noise * 0.5
    if scope == FindScope.FORM:
        base = 5.0 if formish else 1.0
        return base - noise
    # ANY: still penalize noise heavily for short exact queries
    return 3.0 - noise


def text_match_score(
    el: Element,
    *,
    text: str | None,
    name: str | None,
    exact: bool,
) -> float:
    """Score how well element matches text/name query."""
    q_text = (text or "").strip().lower()
    q_name = (name or "").strip().lower()
    el_text = (el.text or "").strip().lower()
    el_name = (el.name or "").strip().lower()
    aria = (el.attributes.get("aria-label") or "").strip().lower()
    href = (el.attributes.get("href") or "").strip().lower()

    score = 0.0
    for q, field_vals in (
        (q_text, (el_text, el_name, aria)),
        (q_name, (el_name, aria, el_text)),
    ):
        if not q:
            continue
        for fv in field_vals:
            if not fv:
                continue
            if exact:
                if fv == q:
                    score += 10.0
                elif fv.startswith(q) and len(fv) <= len(q) + 8:
                    score += 6.0
            else:
                if fv == q:
                    score += 10.0
                elif q in fv:
                    # prefer short fields that contain q (nav labels)
                    # penalize long fields (PR bodies)
                    ratio = len(q) / max(len(fv), 1)
                    score += 4.0 + 6.0 * ratio
                    if len(fv) > 100:
                        score -= 5.0
        # href path segment exact boost e.g. /issues
        if q and f"/{q}" in href and len(q) >= 4:
            score += 8.0
        if q and href.rstrip("/").endswith("/" + q):
            score += 12.0
    return score


def rank_elements(
    elements: Iterable[Element],
    *,
    role: str | None = None,
    name: str | None = None,
    text: str | None = None,
    exact: bool = False,
    scope: FindScope = FindScope.ANY,
) -> list[tuple[float, Element]]:
    """Return elements sorted by grounding score (desc)."""
    role_l = (role or "").lower()
    ranked: list[tuple[float, Element]] = []
    for el in elements:
        if not el.visible:
            continue
        if role_l:
            er = (el.role or "").lower()
            et = (el.type or "").lower()
            # allow tag aliases
            aliases = {
                "link": {"link", "a"},
                "button": {"button"},
                "textbox": {"textbox", "searchbox", "input"},
            }
            allowed = aliases.get(role_l, {role_l})
            if er not in allowed and et not in allowed and er != role_l:
                continue
        s = element_region_score(el, scope) + text_match_score(
            el, text=text, name=name, exact=exact
        )
        if text or name:
            # must have some text match
            if text_match_score(el, text=text, name=name, exact=exact) <= 0:
                continue
        ranked.append((s, el))
    ranked.sort(key=lambda x: (-x[0], x[1].id))
    return ranked


def best_elements(
    elements: list[Element],
    *,
    role: str | None = None,
    name: str | None = None,
    text: str | None = None,
    exact: bool = False,
    scope: FindScope = FindScope.ANY,
    limit: int = 10,
    min_score: float = 2.0,
) -> list[Element]:
    ranked = rank_elements(
        elements, role=role, name=name, text=text, exact=exact, scope=scope
    )
    out = [el for sc, el in ranked if sc >= min_score][:limit]
    # if nav scope empty, fall back to any with higher min
    if not out and scope != FindScope.ANY:
        ranked = rank_elements(
            elements, role=role, name=name, text=text, exact=exact, scope=FindScope.ANY
        )
        out = [el for sc, el in ranked if sc >= min_score + 2][:limit]
    return out
