"""
Agent-oriented page scraping helpers.

Uses semantic snapshots (roles, text, links) rather than raw HTML parsing,
so LLM agents can reason about the same structure they act on.
"""

from __future__ import annotations

from typing import Any

from agent_browser.models.element import Element
from agent_browser.models.snapshot import Snapshot
from agent_browser.page import Page


def elements_to_records(
    elements: list[Element],
    *,
    roles: set[str] | None = None,
    visible_only: bool = True,
) -> list[dict[str, Any]]:
    """Flatten semantic elements into JSON-serializable records."""
    out: list[dict[str, Any]] = []
    for el in elements:
        if visible_only and not el.visible:
            continue
        role = (el.role or "").lower()
        if roles is not None and role not in roles and (el.type or "") not in roles:
            continue
        out.append(
            {
                "id": el.id,
                "role": el.role,
                "type": el.type,
                "name": el.name,
                "text": (el.text or "").strip() or None,
                "href": el.attributes.get("href"),
                "value": el.value,
                "attributes": {
                    k: v
                    for k, v in el.attributes.items()
                    if k in ("id", "class", "href", "src", "alt", "title", "data-testid")
                },
            }
        )
    return out


def snapshot_to_scrape_result(snapshot: Snapshot) -> dict[str, Any]:
    """Build a structured scrape payload from a semantic snapshot."""
    els = snapshot.elements
    headings = [
        e
        for e in els
        if (e.role or "") == "heading" or (e.type or "").startswith("h")
    ]
    links = [e for e in els if (e.role or "") == "link" or e.type == "a"]
    buttons = [e for e in els if (e.role or "") == "button" or e.type == "button"]
    fields = [
        e
        for e in els
        if (e.role or "") in ("textbox", "searchbox", "combobox", "checkbox", "radio")
        or e.type in ("input", "textarea", "select")
    ]

    return {
        "url": snapshot.url,
        "title": snapshot.title,
        "scroll_position": snapshot.scroll_position,
        "counts": {
            "elements": len(els),
            "headings": len(headings),
            "links": len(links),
            "buttons": len(buttons),
            "fields": len(fields),
        },
        "headings": elements_to_records(headings, visible_only=True),
        "links": elements_to_records(links, visible_only=True),
        "buttons": elements_to_records(buttons, visible_only=True),
        "fields": elements_to_records(fields, visible_only=True),
        "all_visible": elements_to_records(els, visible_only=True),
    }


async def scrape_page(
    page: Page,
    *,
    include_raw_html: bool = False,
    include_network: bool = True,
    goal: str | None = None,
) -> dict[str, Any]:
    """
    Scrape the current page using the agent world-model (snapshot + context).

    Returns structured data suitable for an LLM agent or downstream JSON export.
    """
    snap = await page.snapshot(include_raw_html=include_raw_html)
    result = snapshot_to_scrape_result(snap)
    result["context"] = await page.context(
        max_tokens=1500,
        goal=goal or "extract main content and key links",
        refresh=False,
        include_memory=False,
    )
    if include_network:
        result["network"] = page.network_requests()
    if include_raw_html and snap.raw_html:
        result["raw_html_length"] = len(snap.raw_html)
    return result


async def scrape_url(
    url: str,
    *,
    headless: bool = True,
    wait_until: str = "domcontentloaded",
    include_network: bool = True,
    goal: str | None = None,
) -> dict[str, Any]:
    """Open ``url`` in a fresh browser session and scrape it."""
    from agent_browser.browser import Browser

    async with Browser(headless=headless) as browser:
        page = await browser.open(url, wait_until=wait_until)  # type: ignore[arg-type]
        data = await scrape_page(
            page,
            include_network=include_network,
            goal=goal,
        )
        data["session_id"] = browser.session_id
        return data
