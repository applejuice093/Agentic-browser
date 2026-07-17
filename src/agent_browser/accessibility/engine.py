"""AX tree extraction and robust merge into semantic elements (M2/M6)."""

from __future__ import annotations

from typing import Any

from agent_browser.models.element import Element


def _flatten_ax(
    node: dict[str, Any] | None,
    acc: list[dict[str, Any]] | None = None,
    *,
    depth: int = 0,
) -> list[dict[str, Any]]:
    if acc is None:
        acc = []
    if not node:
        return acc
    role = node.get("role")
    skip = {"none", "presentation", "generic", "InlineTextBox", "Ignored"}
    if role and role not in skip:
        acc.append(
            {
                "role": role,
                "name": node.get("name"),
                "description": node.get("description"),
                "value": node.get("value"),
                "checked": node.get("checked"),
                "disabled": node.get("disabled"),
                "expanded": node.get("expanded"),
                "focused": node.get("focused"),
                "pressed": node.get("pressed"),
                "selected": node.get("selected"),
                "level": node.get("level"),
                "depth": depth,
            }
        )
    for child in node.get("children") or []:
        _flatten_ax(child, acc, depth=depth + 1)
    return acc


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _roles_compatible(el_role: str, ax_role: str) -> bool:
    if el_role == ax_role:
        return True
    groups = [
        {"textbox", "searchbox", "input", "combobox"},
        {"button", "submit"},
        {"link", "a"},
        {"img", "image"},
        {"heading", "h1", "h2", "h3", "h4", "h5", "h6"},
        {"checkbox", "switch"},
        {"list", "ul", "ol"},
        {"listitem", "li"},
        {"navigation", "nav"},
        {"main"},
        {"form"},
    ]
    for g in groups:
        if el_role in g and ax_role in g:
            return True
    return False


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

        Scoring: role compatibility + name/text overlap. Each AX node used once.
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
            role = _norm(el.role) or _norm(el.type)
            el_name = _norm(el.name)
            el_text = _norm(el.text)
            best_idx: int | None = None
            best_score = 0

            for idx, ax in enumerate(flat):
                if idx in used:
                    continue
                ax_role = _norm(ax.get("role"))
                if not _roles_compatible(role, ax_role):
                    continue
                ax_name = _norm(ax.get("name"))
                score = 1  # role match baseline
                if el_name and ax_name:
                    if el_name == ax_name:
                        score += 5
                    elif el_name in ax_name or ax_name in el_name:
                        score += 3
                if el_text and ax_name:
                    if el_text == ax_name:
                        score += 4
                    elif el_text in ax_name or ax_name in el_text:
                        score += 2
                if ax.get("focused"):
                    score += 1
                if score > best_score:
                    best_score = score
                    best_idx = idx

            # Soft claim only if AX has a name we lack
            if best_idx is None and not el_name:
                for idx, ax in enumerate(flat):
                    if idx in used:
                        continue
                    if _roles_compatible(role, _norm(ax.get("role"))) and ax.get("name"):
                        best_idx = idx
                        best_score = 1
                        break

            if best_idx is not None and best_score > 0:
                match = flat[best_idx]
                used.add(best_idx)
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
                if match.get("value") is not None and not data.get("value"):
                    data["value"] = str(match["value"])

            merged.append(Element.model_validate(data))

        return merged
