"""Pure scrape helpers (no browser)."""

from __future__ import annotations

from agent_browser.models.element import Element
from agent_browser.models.snapshot import Snapshot
from agent_browser.scrape import elements_to_records, snapshot_to_scrape_result


def _snap(*elements: Element) -> Snapshot:
    return Snapshot(url="https://example.com", title="Example", elements=list(elements))


def test_headings_only_count_h1_to_h6():
    result = snapshot_to_scrape_result(
        _snap(
            Element(id=1, type="h1", text="Title"),
            Element(id=2, type="H3", text="Section"),
            Element(id=3, role="heading", type="div", text="ARIA heading"),
            Element(id=4, type="header", text="Site header"),
            Element(id=5, type="hr"),
            Element(id=6, type="h7", text="Not a heading"),
        )
    )
    assert [h["id"] for h in result["headings"]] == [1, 2, 3]
    assert result["counts"]["headings"] == 3


def test_records_skip_hidden_and_filter_roles():
    els = [
        Element(id=1, role="link", type="a", text=" Docs ", attributes={"href": "/docs"}),
        Element(id=2, role="button", type="button", text="Go", visible=False),
        Element(id=3, role="button", type="button", text="Save", attributes={"onclick": "x()"}),
    ]
    records = elements_to_records(els, roles={"button"})
    assert [r["id"] for r in records] == [3]
    assert "onclick" not in records[0]["attributes"]
    link = elements_to_records(els)[0]
    assert link["text"] == "Docs" and link["href"] == "/docs"
