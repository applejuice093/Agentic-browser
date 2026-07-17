"""Unit tests for stable ID assignment (M2)."""

from agent_browser.semantic.ids import StableIDAssigner, node_fingerprint, secondary_keys


def _node(
    *,
    tag: str = "button",
    role: str = "button",
    text: str = "Go",
    html_id: str | None = None,
    name: str | None = None,
    path: str = "body[0]/button[0]",
) -> dict:
    attrs = {}
    if html_id:
        attrs["id"] = html_id
    if name:
        attrs["name"] = name
    return {
        "type": tag,
        "role": role,
        "text": text,
        "name": name,
        "attributes": attrs,
        "dom_path": path,
        "visible": True,
        "enabled": True,
    }


def test_fingerprint_stable_for_same_node():
    n = _node(html_id="submit")
    assert node_fingerprint(n) == node_fingerprint(dict(n))


def test_fingerprint_differs_for_different_ids():
    a = _node(html_id="a")
    b = _node(html_id="b")
    assert node_fingerprint(a) != node_fingerprint(b)


def test_assign_reuses_ids_across_snapshots():
    assigner = StableIDAssigner()
    first = assigner.assign_nodes(
        [
            _node(html_id="email", tag="input", role="textbox", text="", path="p/input[0]"),
            _node(html_id="go", text="Submit", path="p/button[0]"),
        ]
    )
    id_email = first[0]["id"]
    id_go = first[1]["id"]
    assert id_email != id_go

    # Same nodes again (e.g. re-snapshot) — IDs must not change
    second = assigner.assign_nodes(
        [
            _node(html_id="email", tag="input", role="textbox", text="", path="p/input[0]"),
            _node(html_id="go", text="Submit", path="p/button[0]"),
        ]
    )
    assert second[0]["id"] == id_email
    assert second[1]["id"] == id_go


def test_assign_keeps_id_when_text_changes_but_html_id_same():
    assigner = StableIDAssigner()
    first = assigner.assign_nodes([_node(html_id="status", tag="p", role="p", text="idle")])
    eid = first[0]["id"]
    second = assigner.assign_nodes([_node(html_id="status", tag="p", role="p", text="done")])
    assert second[0]["id"] == eid


def test_new_node_gets_new_id():
    assigner = StableIDAssigner()
    first = assigner.assign_nodes([_node(html_id="a")])
    second = assigner.assign_nodes(
        [
            _node(html_id="a"),
            _node(html_id="b", text="Other", path="p/button[1]"),
        ]
    )
    assert second[0]["id"] == first[0]["id"]
    assert second[1]["id"] != first[0]["id"]


def test_reset_clears_mappings():
    assigner = StableIDAssigner()
    first = assigner.assign_nodes([_node(html_id="a")])
    assigner.reset()
    second = assigner.assign_nodes([_node(html_id="a")])
    # After reset, counter restarts — same node can get id 1 again
    assert second[0]["id"] == 1
    assert first[0]["id"] == 1


def test_secondary_keys_present():
    n = _node(html_id="x", name="q", text="Hello")
    keys = secondary_keys(n)
    assert any(k.startswith("htmlid:") for k in keys)
