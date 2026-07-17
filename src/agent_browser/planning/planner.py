"""Rule-based / LLM-backed plan helper (M7)."""

from __future__ import annotations

from agent_browser.models.snapshot import Snapshot


class Planner:
    """Suggest next steps from page state + goal. Rule-based first; LLM later."""

    def plan(self, snapshot: Snapshot, goal: str) -> list[str]:
        steps: list[str] = [f"Goal: {goal}", f"Current page: {snapshot.title or snapshot.url}"]
        buttons = [e for e in snapshot.elements if e.role in ("button", "link") and e.visible]
        if buttons:
            steps.append(
                f"Candidate actions: "
                + ", ".join(f"[{b.id}] {(b.text or b.name or b.role)}" for b in buttons[:8])
            )
        else:
            steps.append("No obvious interactive candidates in current snapshot.")
        return steps
