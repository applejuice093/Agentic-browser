"""Accessibility-oriented element queries (M6)."""

from __future__ import annotations

from typing import Literal

from agent_browser.models.element import Element

Exactness = Literal["exact", "contains", "startswith"]


def _match_text(hay: str | None, needle: str, how: Exactness) -> bool:
    if hay is None:
        return False
    h = hay.strip()
    n = needle.strip()
    if how == "exact":
        return h.lower() == n.lower()
    if how == "startswith":
        return h.lower().startswith(n.lower())
    return n.lower() in h.lower()


def filter_by_role(
    elements: list[Element],
    role: str,
    *,
    name: str | None = None,
    name_match: Exactness = "contains",
    exact: bool = False,
    visible_only: bool = True,
    enabled_only: bool = False,
) -> list[Element]:
    """
    Filter semantic elements by ARIA/implicit role (Playwright-style).

    If ``exact`` is True, ``name`` uses exact matching.
    """
    if exact and name is not None:
        name_match = "exact"
    role_l = role.lower()
    # Common aliases
    aliases = {
        "textbox": {"textbox", "searchbox", "input"},
        "input": {"textbox", "searchbox", "input"},
        "link": {"link", "a"},
        "button": {"button"},
        "heading": {"heading", "h1", "h2", "h3", "h4", "h5", "h6"},
        "img": {"img", "image"},
        "image": {"img", "image"},
    }
    role_set = aliases.get(role_l, {role_l})

    out: list[Element] = []
    for el in elements:
        if visible_only and not el.visible:
            continue
        if enabled_only and not el.enabled:
            continue
        el_role = (el.role or "").lower()
        el_type = (el.type or "").lower()
        if el_role not in role_set and el_type not in role_set:
            # heading level: role heading or hN
            if role_l == "heading" and el_type.startswith("h") and len(el_type) == 2:
                pass
            else:
                continue
        if name is not None:
            candidates = [el.name, el.text, el.attributes.get("aria-label"), el.attributes.get("title")]
            if not any(_match_text(c if isinstance(c, str) else None, name, name_match) for c in candidates):
                continue
        out.append(el)
    # Prefer named, leaf-ish controls
    out.sort(key=lambda e: (0 if e.name else 1, len(e.children_ids), e.id))
    return out


def filter_by_label(
    elements: list[Element],
    label: str,
    *,
    match: Exactness = "contains",
    visible_only: bool = True,
) -> list[Element]:
    """
    Find controls associated with a label string.

    Matches:
    - element.name / aria-label
    - label elements whose text matches, then sibling/for-linked controls
    - placeholder as weak fallback
    """
    label_els = [
        e
        for e in elements
        if (e.role == "label" or e.type == "label")
        and _match_text(e.text or e.name, label, match)
        and (e.visible or not visible_only)
    ]
    # Controls with accessible name
    named = [
        e
        for e in elements
        if e.type in ("input", "textarea", "select", "button")
        or (e.role or "") in ("textbox", "searchbox", "combobox", "checkbox", "radio", "button")
    ]

    results: list[Element] = []
    seen: set[int] = set()

    for e in named:
        if visible_only and not e.visible:
            continue
        if _match_text(e.name, label, match) or _match_text(
            e.attributes.get("aria-label"), label, match
        ):
            if e.id not in seen:
                results.append(e)
                seen.add(e.id)

    # Label `for` → control id
    for lab in label_els:
        for_id = lab.attributes.get("for")
        if for_id:
            for e in elements:
                if e.attributes.get("id") == for_id and e.id not in seen:
                    if visible_only and not e.visible:
                        continue
                    results.append(e)
                    seen.add(e.id)
        # Children of label
        for cid in lab.children_ids:
            child = next((x for x in elements if x.id == cid), None)
            if child and child.id not in seen:
                if child.type in ("input", "textarea", "select") or child.role in (
                    "textbox",
                    "checkbox",
                    "radio",
                ):
                    results.append(child)
                    seen.add(child.id)

    # Placeholder fallback
    if not results:
        for e in named:
            if visible_only and not e.visible:
                continue
            ph = e.attributes.get("placeholder")
            if _match_text(ph, label, match) and e.id not in seen:
                results.append(e)
                seen.add(e.id)

    return results


def filter_by_placeholder(
    elements: list[Element],
    placeholder: str,
    *,
    match: Exactness = "contains",
    visible_only: bool = True,
) -> list[Element]:
    out: list[Element] = []
    for e in elements:
        if visible_only and not e.visible:
            continue
        if _match_text(e.attributes.get("placeholder"), placeholder, match):
            out.append(e)
    return out


def filter_by_text(
    elements: list[Element],
    text: str,
    *,
    match: Exactness = "contains",
    visible_only: bool = True,
) -> list[Element]:
    out: list[Element] = []
    for e in elements:
        if visible_only and not e.visible:
            continue
        if _match_text(e.text, text, match) or _match_text(e.name, text, match):
            out.append(e)
    out.sort(key=lambda e: (len(e.text or ""), e.id))
    return out


def filter_by_test_id(
    elements: list[Element],
    test_id: str,
    *,
    attr: str = "data-testid",
) -> list[Element]:
    return [e for e in elements if e.attributes.get(attr) == test_id]
