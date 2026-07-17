"""Semantic tree diffing (M3)."""

from __future__ import annotations

from agent_browser.models.diff import Diff
from agent_browser.models.snapshot import Snapshot


class DiffEngine:
    """Compute added/removed/changed elements between snapshots."""

    def diff(self, previous: Snapshot, current: Snapshot) -> Diff:
        prev_by_id = {e.id: e for e in previous.elements}
        curr_by_id = {e.id: e for e in current.elements}

        added = [e for eid, e in curr_by_id.items() if eid not in prev_by_id]
        removed = [eid for eid in prev_by_id if eid not in curr_by_id]
        changed: list[dict] = []
        for eid, curr in curr_by_id.items():
            if eid not in prev_by_id:
                continue
            prev = prev_by_id[eid]
            updates: dict = {"id": eid}
            if prev.text != curr.text:
                updates["text"] = curr.text
            if prev.value != curr.value:
                updates["value"] = curr.value
            if prev.visible != curr.visible:
                updates["visible"] = curr.visible
            if len(updates) > 1:
                changed.append(updates)

        return Diff(added=added, removed=removed, changed=changed)
