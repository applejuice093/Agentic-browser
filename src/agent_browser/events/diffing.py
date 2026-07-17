"""Semantic tree diffing (M3)."""

from __future__ import annotations

from typing import Any

from agent_browser.models.diff import Diff
from agent_browser.models.element import Element
from agent_browser.models.events import BrowserEvent, EventType
from agent_browser.models.snapshot import Snapshot

# Fields compared for "changed" entries
_COMPARE_FIELDS = (
    "text",
    "value",
    "visible",
    "enabled",
    "checked",
    "name",
    "role",
    "description",
)


class DiffEngine:
    """Compute added/removed/changed elements between snapshots."""

    def diff(self, previous: Snapshot, current: Snapshot) -> Diff:
        prev_by_id = {e.id: e for e in previous.elements}
        curr_by_id = {e.id: e for e in current.elements}

        added = [e for eid, e in curr_by_id.items() if eid not in prev_by_id]
        removed = [eid for eid in prev_by_id if eid not in curr_by_id]
        changed: list[dict[str, Any]] = []

        for eid, curr in curr_by_id.items():
            if eid not in prev_by_id:
                continue
            prev = prev_by_id[eid]
            updates = self._element_changes(prev, curr)
            if updates:
                changed.append(updates)

        return Diff(
            added=added,
            removed=removed,
            changed=changed,
            url_changed=previous.url != current.url,
            previous_url=previous.url or None,
            current_url=current.url or None,
            title_changed=previous.title != current.title,
        )

    def _element_changes(self, prev: Element, curr: Element) -> dict[str, Any] | None:
        updates: dict[str, Any] = {"id": curr.id}
        for field in _COMPARE_FIELDS:
            old = getattr(prev, field)
            new = getattr(curr, field)
            if old != new:
                updates[field] = new
                updates[f"previous_{field}"] = old
        # Bounding box shifts (optional, only if significant)
        if prev.bounding_box and curr.bounding_box:
            if (
                abs(prev.bounding_box.x - curr.bounding_box.x) > 1
                or abs(prev.bounding_box.y - curr.bounding_box.y) > 1
                or abs(prev.bounding_box.width - curr.bounding_box.width) > 1
                or abs(prev.bounding_box.height - curr.bounding_box.height) > 1
            ):
                updates["bounding_box"] = curr.bounding_box.model_dump()
        if prev.parent_id != curr.parent_id:
            updates["parent_id"] = curr.parent_id
        if set(prev.children_ids) != set(curr.children_ids):
            updates["children_ids"] = list(curr.children_ids)
        return updates if len(updates) > 1 else None

    def to_events(self, diff: Diff) -> list[BrowserEvent]:
        """Expand a Diff into fine-grained BrowserEvents for streaming agents."""
        events: list[BrowserEvent] = []
        if diff.is_empty:
            return events

        if diff.url_changed:
            events.append(
                BrowserEvent.make(
                    EventType.NAVIGATION,
                    from_url=diff.previous_url,
                    to_url=diff.current_url,
                )
            )

        for el in diff.added:
            events.append(
                BrowserEvent.make(
                    EventType.ELEMENT_ADDED,
                    id=el.id,
                    role=el.role,
                    type=el.type,
                    text=el.text,
                    name=el.name,
                    bounding_box=el.bounding_box.model_dump() if el.bounding_box else None,
                )
            )

        for eid in diff.removed:
            events.append(BrowserEvent.make(EventType.ELEMENT_REMOVED, id=eid))

        for ch in diff.changed:
            if "text" in ch:
                events.append(
                    BrowserEvent.make(
                        EventType.TEXT_CHANGED,
                        id=ch["id"],
                        text=ch.get("text"),
                        previous_text=ch.get("previous_text"),
                    )
                )
            if "value" in ch:
                events.append(
                    BrowserEvent.make(
                        EventType.VALUE_CHANGED,
                        id=ch["id"],
                        value=ch.get("value"),
                        previous_value=ch.get("previous_value"),
                    )
                )

        events.append(
            BrowserEvent.make(
                EventType.PAGE_CHANGED,
                summary=diff.summary(),
                added_ids=[e.id for e in diff.added],
                removed=diff.removed,
                changed_ids=[c["id"] for c in diff.changed],
            )
        )
        return events
