"""Token-aware page context for LLMs (M7)."""

from __future__ import annotations

from agent_browser.models.snapshot import Snapshot


class ContextBuilder:
    """Rank and compress snapshot into an LLM-ready context object."""

    def build(self, snapshot: Snapshot, *, max_tokens: int = 1000) -> dict:
        # Heuristic stub: title + first N interactive elements
        elements = []
        for el in snapshot.elements[:50]:
            if not el.visible:
                continue
            elements.append(
                {
                    "id": el.id,
                    "role": el.role,
                    "text": (el.text or "")[:80],
                    "name": el.name,
                }
            )
        return {
            "title": snapshot.title,
            "url": snapshot.url,
            "elements": elements[: max(1, max_tokens // 20)],
            "alerts": snapshot.alerts,
        }
