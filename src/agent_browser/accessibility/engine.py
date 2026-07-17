"""AX tree extraction and merge into semantic elements (M2)."""

from __future__ import annotations

from typing import Any

from agent_browser.models.element import Element


def _flatten_ax(
    node: dict[str, Any] | None,
    acc: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if acc is None:
        acc = []
    if not node:
        return acc
    role = node.get("role")
    name = node.get("name")
    if role and role not in ("none", "presentation", "generic", "InlineTextBox"):
        acc.append(
            {
                "role": role,
                "name": name,
                "description": node.get("description"),
                "value": node.get("value"),
                "checked": node.get("checked"),
                "disabled": node.get("disabled"),
                "expanded": node.get("expanded"),
                "focused": node.get("focused"),
                "pressed": node.get("pressed"),
                "selected": node.get("selected"),
                "level": node.get("level"),
            }
        )
    for child in node.get("children") or []:
        _flatten_ax(child, acc)
    return acc


class AccessibilityEngine:
    """Builds and merges the browser accessibility tree into semantic objects."""

    async def snapshot(self, page: Any) -> dict[str, Any] | None:
        """
        Return Playwright accessibility snapshot when available.

        Playwright has deprecated ``page.accessibility`` in newer versions;
        we try it and fall back to ``None`` (DOM-derived roles still apply).
        """
        try:
            accessibility = getattr(page, "accessibility", None)
            if accessibility is None:
                return None
            snap = await accessibility.snapshot(interesting_only=True)
            return snap if isinstance(snap, dict) else None
        except Exception:
            return None

    def flatten(self, ax_tree: dict[str, Any] | None) -> list[dict[str, Any]]:
        return _flatten_ax(ax_tree)

    def merge_into_elements(
        self,
        elements: list[Element],
        ax_tree: dict[str, Any] | None,
    ) -> list[Element]:
        """
        Enrich semantic elements with AX role/name/description when missing.

        Matching is heuristic: same role + overlapping name/text.
        """
        if not ax_tree:
            return elements

        flat = self.flatten(ax_tree)
        if not flat:
            return elements

        used: set[int] = set()
        merged: list[Element] = []

        for el in elements:
            data = el.model_dump()
            role = (el.role or "").lower()
            match: dict[str, Any] | None = None
            el_name = (el.name or "").strip().lower()
            el_text = (el.text or "").strip().lower()

            def role_matches(ax_role: str) -> bool:
                if ax_role == role:
                    return True
                if role in ("input", "textbox") and ax_role == "textbox":
                    return True
                if role == "a" and ax_role == "link":
                    return True
                if role == "button" and ax_role == "button":
                    return True
                return False

            for idx, ax in enumerate(flat):
                if idx in used:
                    continue
                ax_role = (ax.get("role") or "").lower()
                if not role_matches(ax_role):
                    continue
                ax_name = (ax.get("name") or "").strip().lower()
                if el_name and ax_name and (
                    el_name == ax_name or el_name in ax_name or ax_name in el_name
                ):
                    match = ax
                    used.add(idx)
                    break
                if el_text and ax_name and (
                    el_text == ax_name or ax_name in el_text or el_text in ax_name
                ):
                    match = ax
                    used.add(idx)
                    break

            # Soft claim: same role, element still missing an accessible name
            if match is None and not el_name:
                for idx, ax in enumerate(flat):
                    if idx in used:
                        continue
                    if role_matches((ax.get("role") or "").lower()) and ax.get("name"):
                        match = ax
                        used.add(idx)
                        break

            if match:
                if not data.get("name") and match.get("name"):
                    data["name"] = match["name"]
                if not data.get("description") and match.get("description"):
                    data["description"] = match["description"]
                ax_role = match.get("role")
                if ax_role and data.get("role") in (None, data.get("type")):
                    data["role"] = ax_role
                if match.get("checked") is not None and data.get("checked") is None:
                    checked = match["checked"]
                    if checked in ("true", True, "mixed"):
                        data["checked"] = True
                    elif checked in ("false", False):
                        data["checked"] = False
                if match.get("disabled") and data.get("enabled") is True:
                    data["enabled"] = False

            merged.append(Element.model_validate(data))

        return merged
