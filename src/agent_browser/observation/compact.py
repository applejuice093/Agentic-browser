"""Build compact LLM observations from snapshots + diffs."""

from __future__ import annotations

from typing import Any

from agent_browser.models.diff import Diff
from agent_browser.models.element import Element
from agent_browser.models.network import NetworkRequest
from agent_browser.models.observation import (
    DetailLevel,
    DiffSummary,
    InteractiveRef,
    NetworkHint,
    Observation,
)
from agent_browser.models.snapshot import Snapshot

INTERACTIVE_ROLES = frozenset(
    {
        "button",
        "link",
        "textbox",
        "searchbox",
        "checkbox",
        "radio",
        "combobox",
        "listbox",
        "menuitem",
        "tab",
        "switch",
        "slider",
        "option",
        "spinbutton",
    }
)
INTERACTIVE_TAGS = frozenset(
    {"a", "button", "input", "select", "textarea", "summary", "option"}
)
LANDMARK_ROLES = frozenset(
    {"navigation", "main", "banner", "contentinfo", "form", "search", "complementary"}
)


def _approx_tokens(obj: Any) -> int:
    import json

    try:
        s = json.dumps(obj, default=str)
    except Exception:
        s = str(obj)
    return max(1, len(s) // 4)


def element_to_ref(
    el: Element,
    *,
    include_box: bool = False,
    text_limit: int = 80,
) -> InteractiveRef:
    text = (el.text or "").strip()
    if len(text) > text_limit:
        text = text[: text_limit - 1] + "…"
    name = (el.name or "").strip() or None
    if name and len(name) > text_limit:
        name = name[: text_limit - 1] + "…"
    href = el.attributes.get("href")
    placeholder = el.attributes.get("placeholder")
    box = None
    if include_box and el.bounding_box is not None:
        box = el.bounding_box.model_dump()
    value = el.value
    if value is not None and len(value) > 40:
        value = value[:39] + "…"
    return InteractiveRef(
        ref=el.id,
        role=el.role,
        name=name,
        text=text or None,
        tag=el.type,
        value=value,
        href=href,
        visible=el.visible,
        enabled=el.enabled,
        checked=el.checked,
        placeholder=placeholder,
        box=box,
    )


def is_interactive(el: Element) -> bool:
    role = (el.role or "").lower()
    tag = (el.type or "").lower()
    if role in INTERACTIVE_ROLES or tag in INTERACTIVE_TAGS:
        return True
    if el.attributes.get("onclick") or el.attributes.get("tabindex"):
        return True
    return False


def is_heading(el: Element) -> bool:
    role = (el.role or "").lower()
    tag = (el.type or "").lower()
    return role == "heading" or tag in {"h1", "h2", "h3", "h4", "h5", "h6"}


def is_landmark(el: Element) -> bool:
    return (el.role or "").lower() in LANDMARK_ROLES


def select_elements(
    elements: list[Element],
    detail: DetailLevel,
) -> tuple[list[Element], list[Element], bool]:
    """Return (interactive, headings, truncated_flag_hint)."""
    interactive = [e for e in elements if e.visible and is_interactive(e)]
    headings = [e for e in elements if e.visible and is_heading(e)]
    if detail == DetailLevel.SPARSE:
        # prefer enabled controls; cap later by tokens
        interactive = [e for e in interactive if e.enabled or e.role in ("link", "button")]
        headings = headings[:6]
    elif detail == DetailLevel.NORMAL:
        # add landmarks as non-interactive context via headings list? keep separate
        pass
    else:  # FULL — interactive still filtered; caller may dump all
        pass
    return interactive, headings, False


def diff_to_summary(diff: Diff | None) -> DiffSummary | None:
    if diff is None:
        return None
    return DiffSummary(
        added=len(diff.added),
        removed=len(diff.removed),
        changed=len(diff.changed),
        url_changed=diff.url_changed,
        title_changed=diff.title_changed,
        added_refs=[e.id for e in diff.added[:40]],
        removed_refs=list(diff.removed[:40]),
        changed_refs=[c.get("id") for c in diff.changed[:40] if c.get("id") is not None],
    )


def network_to_hints(
    requests: list[NetworkRequest],
    *,
    limit: int = 8,
) -> list[NetworkHint]:
    # Prefer recent API-like calls
    ranked = sorted(requests, key=lambda r: r.timestamp, reverse=True)
    hints: list[NetworkHint] = []
    for r in ranked:
        if r.resource_type not in ("xhr", "fetch", "other", None) and not r.is_graphql:
            if "/api" not in r.url and "graphql" not in r.url.lower():
                continue
        hints.append(
            NetworkHint(
                url=r.url[:200],
                method=r.method,
                status=r.response_status,
                is_graphql=r.is_graphql,
                graphql_query_name=r.graphql_query_name,
                failed=r.failed,
            )
        )
        if len(hints) >= limit:
            break
    return hints


def build_observation(
    snapshot: Snapshot,
    *,
    detail: DetailLevel = DetailLevel.NORMAL,
    diff: Diff | None = None,
    network: list[NetworkRequest] | None = None,
    max_tokens: int = 2000,
    max_interactive: int = 60,
    max_headings: int = 12,
    include_boxes: bool = False,
    step: int = 0,
    note: str | None = None,
    errors: list[str] | None = None,
) -> Observation:
    """
    Compress a Snapshot into an LLM-friendly Observation under ``max_tokens``.
    """
    if detail == DetailLevel.FULL:
        interactive_els = [e for e in snapshot.elements if e.visible]
        heading_els: list[Element] = []
    else:
        interactive_els, heading_els, _ = select_elements(snapshot.elements, detail)

    # Prefer interactive, enabled, shorter names first for ranking
    def rank(e: Element) -> tuple:
        role = (e.role or "").lower()
        prio = 0
        if role in ("button", "link", "textbox", "searchbox"):
            prio = 3
        elif is_interactive(e):
            prio = 2
        return (-prio, 0 if e.enabled else 1, e.id)

    interactive_els = sorted(interactive_els, key=rank)
    heading_els = heading_els[:max_headings]

    include_box = include_boxes or detail == DetailLevel.FULL
    text_limit = 48 if detail == DetailLevel.SPARSE else 80

    refs: list[InteractiveRef] = []
    truncated = False
    for el in interactive_els:
        if len(refs) >= max_interactive:
            truncated = True
            break
        refs.append(element_to_ref(el, include_box=include_box, text_limit=text_limit))

    headings = [
        element_to_ref(e, include_box=False, text_limit=text_limit) for e in heading_els
    ]

    obs = Observation(
        url=snapshot.url,
        title=snapshot.title,
        detail=detail,
        interactive=refs,
        headings=headings if detail != DetailLevel.SPARSE else headings[:4],
        diff=diff_to_summary(diff),
        network=network_to_hints(network or []),
        errors=list(errors or []),
        alerts=list(snapshot.alerts),
        scroll_position=snapshot.scroll_position,
        element_total=len(snapshot.elements),
        interactive_total=len(interactive_els),
        truncated=truncated,
        step=step,
        note=note,
    )

    # Token budget: drop tails until under max
    data = obs.to_llm_dict()
    tokens = _approx_tokens(data)
    while tokens > max_tokens and len(obs.interactive) > 8:
        obs.interactive = obs.interactive[:-5]
        obs.truncated = True
        tokens = _approx_tokens(obs.to_llm_dict())
    while tokens > max_tokens and len(obs.headings) > 2:
        obs.headings = obs.headings[:-2]
        obs.truncated = True
        tokens = _approx_tokens(obs.to_llm_dict())
    if tokens > max_tokens and obs.network:
        obs.network = obs.network[:3]
        tokens = _approx_tokens(obs.to_llm_dict())
    obs.approx_tokens = tokens
    return obs
