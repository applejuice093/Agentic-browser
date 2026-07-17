"""Semantic DOM builder: extract, filter, stable IDs, tree links, AX merge (M2)."""

from __future__ import annotations

from typing import Any

from agent_browser.accessibility.engine import AccessibilityEngine
from agent_browser.models.element import Element
from agent_browser.models.snapshot import Snapshot
from agent_browser.semantic.extract import SEMANTIC_EXTRACT_JS, STAMP_IDS_JS
from agent_browser.semantic.ids import StableIDAssigner


class SemanticDOMEngine:
    """
    Builds a semantic element graph from the live page.

    Pipeline:
      1. Extract semantic candidates in-page (filter layout noise)
      2. Assign stable integer IDs across snapshots
      3. Stamp ``data-agent-id`` for action targeting
      4. Merge accessibility tree hints (role/name/description)
      5. Wire parent_id / children_ids
    """

    def __init__(
        self,
        *,
        id_assigner: StableIDAssigner | None = None,
        accessibility: AccessibilityEngine | None = None,
    ) -> None:
        self.ids = id_assigner or StableIDAssigner()
        self.a11y = accessibility or AccessibilityEngine()
        self._elements: dict[int, Element] = {}
        self._last_snapshot: Snapshot | None = None

    def reset(self) -> None:
        """Reset session identity (call after top-level navigation)."""
        self.ids.reset()
        self._elements.clear()
        self._last_snapshot = None

    @property
    def elements(self) -> dict[int, Element]:
        return dict(self._elements)

    async def capture(
        self,
        page: Any,
        *,
        url: str,
        title: str,
        scroll_position: float = 0.0,
        include_raw_html: bool = False,
        merge_accessibility: bool = True,
    ) -> Snapshot:
        """Extract semantic snapshot from a Playwright page."""
        raw_nodes: list[dict[str, Any]] = await page.evaluate(SEMANTIC_EXTRACT_JS)
        if not isinstance(raw_nodes, list):
            raw_nodes = []

        # Drop pure layout leftovers: invisible generic divs with no name/text/role value
        filtered = [n for n in raw_nodes if self._keep_node(n)]

        assigned = self.ids.assign_nodes(filtered)

        # Stamp stable ids into the live DOM
        stamp_map = [
            {"path": n.get("dom_path"), "id": n["id"]}
            for n in assigned
            if n.get("dom_path")
        ]
        if stamp_map:
            await page.evaluate(STAMP_IDS_JS, stamp_map)

        elements = [self._to_element(n) for n in assigned]
        elements = self._wire_tree(elements, assigned)

        if merge_accessibility:
            ax = await self.a11y.snapshot(page)
            elements = self.a11y.merge_into_elements(elements, ax)

        raw_html: str | None = None
        if include_raw_html:
            raw_html = await page.content()

        snap = Snapshot(
            url=url,
            title=title,
            scroll_position=scroll_position,
            elements=elements,
            raw_html=raw_html,
        )
        self._elements = {e.id: e for e in elements}
        self._last_snapshot = snap
        return snap

    def build(self, raw_dom: Any, ax_tree: Any | None = None) -> Snapshot:
        """
        Synchronous build from pre-extracted node list (tests / offline).

        ``raw_dom`` should be a list of node dicts as produced by the extract script.
        """
        if not isinstance(raw_dom, list):
            raise TypeError("raw_dom must be a list of node dicts")
        filtered = [n for n in raw_dom if self._keep_node(n)]
        assigned = self.ids.assign_nodes(filtered)
        elements = [self._to_element(n) for n in assigned]
        elements = self._wire_tree(elements, assigned)
        if ax_tree:
            elements = self.a11y.merge_into_elements(elements, ax_tree)
        snap = Snapshot(url="", title="", elements=elements)
        self._elements = {e.id: e for e in elements}
        self._last_snapshot = snap
        return snap

    def query(
        self,
        *,
        role: str | None = None,
        text_contains: str | None = None,
        name: str | None = None,
        type: str | None = None,  # noqa: A002
        visible_only: bool = True,
        enabled_only: bool = False,
    ) -> list[Element]:
        """Query the last captured semantic model."""
        results: list[Element] = []
        for el in self._elements.values():
            if visible_only and not el.visible:
                continue
            if enabled_only and not el.enabled:
                continue
            if role is not None and (el.role or "").lower() != role.lower():
                continue
            if type is not None and (el.type or "").lower() != type.lower():
                continue
            if text_contains is not None:
                hay = (el.text or "").lower()
                if text_contains.lower() not in hay:
                    continue
            if name is not None:
                hay = (el.name or "").lower()
                if name.lower() not in hay:
                    continue
            results.append(el)
        # Prefer smaller / more specific nodes first (deeper in tree)
        results.sort(key=lambda e: (len(e.children_ids), e.id))
        return results

    def get(self, element_id: int) -> Element | None:
        return self._elements.get(element_id)

    # --- helpers ---

    @staticmethod
    def _keep_node(node: dict[str, Any]) -> bool:
        role = (node.get("role") or "").lower()
        tag = (node.get("type") or "").lower()
        text = (node.get("text") or "").strip()
        name = (node.get("name") or "").strip()
        # Always keep interactive / landmark-ish roles
        keep_roles = {
            "button",
            "link",
            "textbox",
            "checkbox",
            "radio",
            "combobox",
            "listbox",
            "menuitem",
            "tab",
            "heading",
            "img",
            "form",
            "navigation",
            "main",
            "banner",
            "contentinfo",
            "complementary",
            "search",
            "dialog",
            "list",
            "listitem",
            "table",
            "label",
            "slider",
            "switch",
            "option",
        }
        if role in keep_roles:
            return True
        if tag in {
            "button",
            "a",
            "input",
            "select",
            "textarea",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "form",
            "nav",
            "main",
            "img",
            "label",
            "li",
        }:
            return True
        if name:
            return True
        if text and tag not in ("div", "span"):
            return True
        # Drop empty generic layout nodes
        if tag in ("div", "span") and not text and not name and role == tag:
            return False
        return bool(text or name)

    @staticmethod
    def _to_element(node: dict[str, Any]) -> Element:
        payload = {
            "id": node["id"],
            "role": node.get("role"),
            "type": node.get("type"),
            "text": node.get("text"),
            "attributes": node.get("attributes") or {},
            "value": node.get("value"),
            "checked": node.get("checked"),
            "visible": bool(node.get("visible", True)),
            "enabled": bool(node.get("enabled", True)),
            "bounding_box": node.get("bounding_box"),
            "parent_id": None,
            "children_ids": [],
            "name": node.get("name"),
            "description": node.get("description"),
        }
        return Element.model_validate(payload)

    @staticmethod
    def _wire_tree(
        elements: list[Element],
        assigned: list[dict[str, Any]],
    ) -> list[Element]:
        path_to_id = {
            n["dom_path"]: int(n["id"]) for n in assigned if n.get("dom_path")
        }
        parent_for: dict[int, int | None] = {}
        children_for: dict[int, list[int]] = {e.id: [] for e in elements}

        for n in assigned:
            eid = int(n["id"])
            parent_path = n.get("parent_path")
            parent_id = path_to_id.get(parent_path) if parent_path else None
            parent_for[eid] = parent_id
            if parent_id is not None and parent_id in children_for:
                children_for[parent_id].append(eid)

        wired: list[Element] = []
        for el in elements:
            data = el.model_dump()
            data["parent_id"] = parent_for.get(el.id)
            data["children_ids"] = children_for.get(el.id, [])
            wired.append(Element.model_validate(data))
        return wired
