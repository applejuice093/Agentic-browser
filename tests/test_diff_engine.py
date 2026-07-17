"""Unit tests for DiffEngine (M3)."""

from agent_browser.events.diffing import DiffEngine
from agent_browser.models.element import Element
from agent_browser.models.events import EventType
from agent_browser.models.snapshot import Snapshot


def _snap(*elements: Element, url: str = "https://a.test", title: str = "A") -> Snapshot:
    return Snapshot(url=url, title=title, elements=list(elements))


def test_diff_added_removed_changed():
    prev = _snap(
        Element(id=1, role="button", text="A"),
        Element(id=2, role="link", text="B"),
        Element(id=3, role="textbox", text="", value="old"),
    )
    curr = _snap(
        Element(id=1, role="button", text="A updated"),
        Element(id=3, role="textbox", text="", value="new"),
        Element(id=4, role="button", text="C"),
    )
    diff = DiffEngine().diff(prev, curr)
    assert [e.id for e in diff.added] == [4]
    assert diff.removed == [2]
    changed_ids = {c["id"] for c in diff.changed}
    assert 1 in changed_ids
    assert 3 in changed_ids
    text_change = next(c for c in diff.changed if c["id"] == 1)
    assert text_change["text"] == "A updated"
    assert text_change["previous_text"] == "A"
    val_change = next(c for c in diff.changed if c["id"] == 3)
    assert val_change["value"] == "new"


def test_diff_empty():
    el = Element(id=1, role="button", text="X")
    snap = _snap(el)
    diff = DiffEngine().diff(snap, snap.model_copy(deep=True))
    assert diff.is_empty
    assert diff.summary()["is_empty"] is True


def test_url_and_title_change():
    prev = _snap(url="https://a", title="A")
    curr = _snap(url="https://b", title="B")
    diff = DiffEngine().diff(prev, curr)
    assert diff.url_changed
    assert diff.title_changed
    assert not diff.is_empty


def test_to_events():
    prev = _snap(Element(id=1, role="button", text="A"))
    curr = _snap(
        Element(id=1, role="button", text="B"),
        Element(id=2, role="link", text="L"),
        url="https://a.test",
        title="A",
    )
    # force remove nothing; add 2, change 1
    engine = DiffEngine()
    diff = engine.diff(prev, curr)
    events = engine.to_events(diff)
    types = [
        e.event.value if hasattr(e.event, "value") else e.event for e in events
    ]
    assert EventType.ELEMENT_ADDED.value in types
    assert EventType.TEXT_CHANGED.value in types
    assert EventType.PAGE_CHANGED.value in types
