"""Token-aware page context for LLMs (M7)."""

from __future__ import annotations

from typing import Any

from agent_browser.models.snapshot import Snapshot


def _approx_tokens(text: str) -> int:
    # Rough heuristic: ~4 chars per token
    return max(1, len(text) // 4)


class ContextBuilder:
    """Rank and compress snapshot into an LLM-ready context object."""

    PRIORITY_ROLES = {
        "button": 10,
        "link": 9,
        "textbox": 10,
        "searchbox": 10,
        "checkbox": 8,
        "radio": 8,
        "combobox": 9,
        "heading": 7,
        "form": 6,
        "navigation": 5,
        "main": 4,
        "alert": 12,
        "dialog": 11,
    }

    def build(
        self,
        snapshot: Snapshot,
        *,
        max_tokens: int = 1000,
        goal: str | None = None,
        memory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ranked = sorted(
            [e for e in snapshot.elements if e.visible],
            key=lambda e: (
                -self.PRIORITY_ROLES.get((e.role or "").lower(), 1),
                0 if e.enabled else 1,
                e.id,
            ),
        )

        elements: list[dict[str, Any]] = []
        used = 0
        budget = max(50, max_tokens)

        header_bits = [
            f"title={snapshot.title}",
            f"url={snapshot.url}",
        ]
        if goal:
            header_bits.append(f"goal={goal}")
        used += _approx_tokens(" ".join(header_bits))

        forms: list[dict[str, Any]] = []
        buttons: list[dict[str, Any]] = []
        errors = list(snapshot.alerts)

        for el in ranked:
            entry = {
                "id": el.id,
                "role": el.role,
                "type": el.type,
                "text": (el.text or "")[:120],
                "name": el.name,
                "value": (el.value[:40] + "…") if el.value and len(el.value) > 40 else el.value,
                "enabled": el.enabled,
            }
            cost = _approx_tokens(str(entry))
            if used + cost > budget and elements:
                break
            used += cost
            elements.append(entry)
            role = (el.role or "").lower()
            if role in ("textbox", "searchbox", "checkbox", "radio", "combobox") or el.type in (
                "input",
                "textarea",
                "select",
            ):
                forms.append({"id": el.id, "name": el.name or el.attributes.get("name"), "role": el.role})
            if role in ("button", "link") or el.type == "button":
                buttons.append({"id": el.id, "text": el.text or el.name})

        ctx: dict[str, Any] = {
            "title": snapshot.title,
            "url": snapshot.url,
            "scroll_position": snapshot.scroll_position,
            "current_goal": goal,
            "forms": forms[:20],
            "buttons": buttons[:20],
            "errors": errors,
            "elements": elements,
            "approx_tokens": used,
            "element_total": len(snapshot.elements),
            "element_included": len(elements),
            "truncated": len(elements) < len([e for e in snapshot.elements if e.visible]),
        }
        if memory:
            ctx["memory"] = memory
        return ctx
