"""Offline unit tests for SemanticDOMEngine (no browser)."""

from agent_browser.accessibility.engine import AccessibilityEngine
from agent_browser.semantic.engine import SemanticDOMEngine


def _raw(
    *,
    tag: str,
    role: str,
    text: str = "",
    name: str | None = None,
    path: str,
    parent_path: str | None = None,
    html_id: str | None = None,
    visible: bool = True,
) -> dict:
    attrs = {}
    if html_id:
        attrs["id"] = html_id
    return {
        "type": tag,
        "role": role,
        "text": text,
        "name": name,
        "description": None,
        "attributes": attrs,
        "value": None,
        "checked": None,
        "visible": visible,
        "enabled": True,
        "bounding_box": {"x": 0, "y": 0, "width": 10, "height": 10},
        "dom_path": path,
        "parent_path": parent_path,
        "depth": path.count("/") + 1,
    }


def test_build_tree_parent_children():
    engine = SemanticDOMEngine()
    form_path = "body[0]/form[0]"
    btn_path = "body[0]/form[0]/button[0]"
    snap = engine.build(
        [
            _raw(tag="form", role="form", path=form_path, html_id="login"),
            _raw(
                tag="button",
                role="button",
                text="Submit",
                path=btn_path,
                parent_path=form_path,
                html_id="submit",
            ),
        ]
    )
    by_id = {e.id: e for e in snap.elements}
    form = next(e for e in snap.elements if e.type == "form")
    btn = next(e for e in snap.elements if e.type == "button")
    assert btn.parent_id == form.id
    assert btn.id in form.children_ids
    assert form.parent_id is None
    assert by_id[btn.id].role == "button"


def test_query_by_role_and_text():
    engine = SemanticDOMEngine()
    engine.build(
        [
            _raw(tag="button", role="button", text="Checkout", path="b[0]", html_id="c"),
            _raw(tag="button", role="button", text="Cancel", path="b[1]", html_id="x"),
            _raw(tag="a", role="link", text="Home", path="a[0]", html_id="h"),
        ]
    )
    found = engine.query(role="button", text_contains="Check")
    assert len(found) == 1
    assert found[0].text == "Checkout"
    links = engine.query(role="link")
    assert len(links) == 1


def test_filters_empty_layout_divs():
    engine = SemanticDOMEngine()
    snap = engine.build(
        [
            _raw(tag="div", role="div", text="", path="d[0]"),
            _raw(tag="button", role="button", text="OK", path="d[0]/b[0]", html_id="ok"),
        ]
    )
    types = {e.type for e in snap.elements}
    assert "button" in types
    # empty layout div dropped
    assert "div" not in types or all(e.text or e.name for e in snap.elements if e.type == "div")


def test_stable_ids_via_engine_across_builds():
    engine = SemanticDOMEngine()
    s1 = engine.build(
        [_raw(tag="button", role="button", text="A", path="b[0]", html_id="a")]
    )
    id_a = s1.elements[0].id
    s2 = engine.build(
        [
            _raw(tag="button", role="button", text="A", path="b[0]", html_id="a"),
            _raw(tag="button", role="button", text="B", path="b[1]", html_id="b"),
        ]
    )
    by_html = {e.attributes.get("id"): e.id for e in s2.elements}
    assert by_html["a"] == id_a
    assert by_html["b"] != id_a


def test_ax_merge_enriches_name():
    engine = SemanticDOMEngine()
    ax_tree = {
        "role": "RootWebArea",
        "name": "Page",
        "children": [
            {"role": "button", "name": "Accessible Submit", "children": []},
        ],
    }
    # Button without name in DOM
    snap = engine.build(
        [_raw(tag="button", role="button", text="Submit", path="b[0]", html_id="s")],
        ax_tree=ax_tree,
    )
    btn = snap.elements[0]
    assert btn.name == "Accessible Submit"


def test_accessibility_flatten():
    ax = {
        "role": "RootWebArea",
        "children": [
            {"role": "heading", "name": "Hi", "children": []},
            {"role": "none", "name": "", "children": []},
        ],
    }
    flat = AccessibilityEngine().flatten(ax)
    roles = [n["role"] for n in flat]
    assert "heading" in roles
    assert "none" not in roles
