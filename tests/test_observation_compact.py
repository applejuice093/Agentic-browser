"""Unit tests for compact observation helpers (no Playwright)."""

from __future__ import annotations

from agent_browser.models.diff import Diff
from agent_browser.models.element import BoundingBox, Element
from agent_browser.models.network import NetworkRequest
from agent_browser.models.observation import DetailLevel
from agent_browser.models.snapshot import Snapshot
from agent_browser.observation.compact import (
    build_observation,
    diff_to_summary,
    element_to_ref,
    is_heading,
    is_interactive,
    is_landmark,
    network_to_hints,
    select_elements,
)


def _el(**kwargs) -> Element:
    defaults = {
        "id": 1,
        "role": "button",
        "type": "button",
        "text": "Go",
        "visible": True,
        "enabled": True,
        "attributes": {},
    }
    defaults.update(kwargs)
    return Element(**defaults)


def test_is_interactive_by_role_and_tag():
    assert is_interactive(_el(role="link", type="a", text="Home"))
    assert is_interactive(_el(role=None, type="input", text=""))
    assert not is_interactive(_el(role="heading", type="h1", text="Title"))


def test_is_interactive_onclick_or_tabindex():
    assert is_interactive(_el(role=None, type="div", attributes={"onclick": "x()"}))
    assert is_interactive(_el(role=None, type="div", attributes={"tabindex": "0"}))


def test_is_heading_and_landmark():
    assert is_heading(_el(role="heading", type="h2", text="Section"))
    assert is_heading(_el(role=None, type="h3", text="Sub"))
    assert is_landmark(_el(role="navigation", type="nav", text=""))
    assert not is_landmark(_el(role="button", type="button", text="Go"))


def test_element_to_ref_truncates_long_text_and_value():
    el = _el(
        id=7,
        text="x" * 120,
        name="n" * 120,
        value="v" * 80,
        attributes={"href": "/path", "placeholder": "Search"},
        bounding_box=BoundingBox(x=1, y=2, width=3, height=4),
    )
    ref = element_to_ref(el, include_box=True, text_limit=80)
    assert ref.ref == 7
    assert ref.text is not None and len(ref.text) == 80 and ref.text.endswith("…")
    assert ref.name is not None and ref.name.endswith("…")
    assert ref.value is not None and ref.value.endswith("…")
    assert ref.href == "/path"
    assert ref.placeholder == "Search"
    assert ref.box == {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}


def test_select_elements_sparse_limits_headings():
    elements = [
        _el(id=1, role="button", type="button", text="Ok", enabled=True),
        _el(id=2, role="button", type="button", text="Disabled", enabled=False),
        _el(id=3, role="heading", type="h1", text="One"),
        _el(id=4, role="heading", type="h2", text="Two"),
        _el(id=5, role="heading", type="h2", text="Three"),
        _el(id=6, role="heading", type="h2", text="Four"),
        _el(id=7, role="heading", type="h2", text="Five"),
        _el(id=8, role="heading", type="h2", text="Six"),
        _el(id=9, role="heading", type="h2", text="Seven"),
        _el(id=10, role="link", type="a", text="Docs", enabled=False),
    ]
    interactive, headings, _ = select_elements(elements, DetailLevel.SPARSE)
    assert all(e.enabled or e.role in ("link", "button") for e in interactive)
    assert len(headings) <= 6


def test_diff_to_summary_none_and_counts():
    assert diff_to_summary(None) is None
    diff = Diff(
        added=[_el(id=2, text="New")],
        removed=[1],
        changed=[{"id": 3, "fields": ["text"]}],
        url_changed=True,
        title_changed=False,
    )
    summary = diff_to_summary(diff)
    assert summary is not None
    assert summary.added == 1
    assert summary.removed == 1
    assert summary.changed == 1
    assert summary.url_changed is True
    assert summary.added_refs == [2]
    assert summary.removed_refs == [1]
    assert summary.changed_refs == [3]


def test_network_to_hints_prefers_api_like():
    reqs = [
        NetworkRequest(
            id="1",
            url="https://cdn.example.com/app.js",
            method="GET",
            resource_type="script",
            timestamp=1.0,
        ),
        NetworkRequest(
            id="2",
            url="https://api.example.com/v1/items",
            method="GET",
            resource_type="xhr",
            timestamp=2.0,
            response_status=200,
        ),
        NetworkRequest(
            id="3",
            url="https://example.com/graphql",
            method="POST",
            resource_type="fetch",
            timestamp=3.0,
            is_graphql=True,
            graphql_query_name="GetItems",
        ),
    ]
    hints = network_to_hints(reqs, limit=2)
    assert len(hints) == 2
    assert hints[0].url.endswith("/graphql")
    assert hints[0].is_graphql is True
    assert hints[1].url.endswith("/v1/items")


def test_build_observation_truncates_under_token_budget():
    elements = [
        _el(id=i, role="button", type="button", text=f"Action {i} " + ("word " * 10))
        for i in range(1, 40)
    ]
    snap = Snapshot(
        url="https://example.com",
        title="Demo",
        elements=elements,
    )
    obs = build_observation(snap, detail=DetailLevel.NORMAL, max_tokens=400, max_interactive=40)
    assert obs.url == "https://example.com"
    assert obs.title == "Demo"
    assert obs.approx_tokens <= 400 or obs.truncated
    assert len(obs.interactive) < 40 or obs.truncated
    assert obs.summary
