"""Unit tests for core data models (no browser required)."""

from agent_browser.models.diff import Diff
from agent_browser.models.element import BoundingBox, Element
from agent_browser.models.events import BrowserEvent, EventType
from agent_browser.models.snapshot import Snapshot
from agent_browser.events.diffing import DiffEngine
from agent_browser.memory.store import MemoryStore
from agent_browser.planning.context import ContextBuilder
from agent_browser.planning.planner import Planner
from agent_browser import __version__


def test_version():
    assert __version__ == "0.2.1"


def test_element_roundtrip():
    el = Element(
        id=1,
        role="button",
        type="button",
        text="Checkout",
        visible=True,
        bounding_box=BoundingBox(x=10, y=20, width=100, height=32),
    )
    data = el.model_dump()
    restored = Element.model_validate(data)
    assert restored.id == 1
    assert restored.text == "Checkout"
    assert restored.bounding_box is not None
    assert restored.bounding_box.width == 100


def test_snapshot_defaults():
    snap = Snapshot(url="https://example.com", title="Example")
    assert snap.elements == []
    assert snap.scroll_position == 0.0


def test_diff_engine():
    prev = Snapshot(
        url="https://example.com",
        elements=[
            Element(id=1, role="button", text="A"),
            Element(id=2, role="link", text="B"),
        ],
    )
    curr = Snapshot(
        url="https://example.com",
        elements=[
            Element(id=1, role="button", text="A updated"),
            Element(id=3, role="button", text="C"),
        ],
    )
    diff = DiffEngine().diff(prev, curr)
    assert isinstance(diff, Diff)
    assert [e.id for e in diff.added] == [3]
    assert diff.removed == [2]
    assert any(c["id"] == 1 and c.get("text") == "A updated" for c in diff.changed)


def test_event_model():
    ev = BrowserEvent(event=EventType.NAVIGATION, timestamp=1.0, data={"to": "https://x"})
    assert ev.event == EventType.NAVIGATION
    assert ev.data["to"] == "https://x"


def test_memory_store():
    mem = MemoryStore("sess-1")
    mem.set("email", "user@example.com")
    mem.log_url("https://example.com")
    mem.log_action({"type": "click", "id": 1})
    assert mem.get("email") == "user@example.com"
    summary = mem.summary()
    assert summary["action_count"] == 1
    assert "https://example.com" in summary["urls"]


def test_context_and_planner():
    snap = Snapshot(
        url="https://shop.example.com",
        title="Shop",
        elements=[
            Element(id=1, role="button", text="Add to Cart", visible=True),
            Element(id=2, role="link", text="Home", visible=True),
        ],
    )
    ctx = ContextBuilder().build(snap, max_tokens=500)
    assert ctx["title"] == "Shop"
    assert len(ctx["elements"]) >= 1

    plan = Planner().plan(snap, "add item to cart")
    assert any("Goal" in s for s in plan)
    assert any("Suggested" in s or "Candidate" in s or "action" in s.lower() for s in plan)
