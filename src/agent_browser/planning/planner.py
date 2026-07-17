"""Rule-based planning helper (M7)."""

from __future__ import annotations

import re
from typing import Any

from agent_browser.models.snapshot import Snapshot


class Planner:
    """Suggest next steps from page state + goal. Rule-based (no LLM required)."""

    def plan(self, snapshot: Snapshot, goal: str) -> list[str]:
        steps: list[str] = [
            f"Goal: {goal}",
            f"Current page: {snapshot.title or snapshot.url}",
        ]
        g = goal.lower()
        actions = self.suggest_actions(snapshot, goal)
        if actions:
            steps.append("Suggested actions:")
            for a in actions:
                steps.append(
                    f"  - {a['action']} id={a.get('element_id')} "
                    f"({a.get('role')}: {a.get('label')}) — {a.get('reason')}"
                )
        else:
            steps.append("No high-confidence action candidates; inspect snapshot.elements.")
        if any(k in g for k in ("login", "sign in", "signin")):
            steps.append("Hint: fill credentials then click a submit/login button.")
        if any(k in g for k in ("search", "find", "query")):
            steps.append("Hint: locate searchbox/textbox, fill query, submit.")
        if any(k in g for k in ("checkout", "purchase", "buy", "pay")):
            steps.append("Hint: find cart/checkout buttons; verify forms before submit.")
        return steps

    def suggest_actions(self, snapshot: Snapshot, goal: str) -> list[dict[str, Any]]:
        g = goal.lower()
        keywords = set(re.findall(r"[a-z0-9]+", g))
        stop = {"the", "a", "an", "to", "and", "or", "for", "on", "in", "of", "with", "my"}
        keywords -= stop

        scored: list[tuple[float, dict[str, Any]]] = []
        for el in snapshot.elements:
            if not el.visible or not el.enabled:
                continue
            label = " ".join(
                x for x in [(el.text or ""), (el.name or ""), (el.role or "")] if x
            ).lower()
            score = 0.0
            for kw in keywords:
                if kw in label:
                    score += 2.0
            role = (el.role or "").lower()
            if role in ("button", "link") and score > 0:
                score += 1.5
            if role in ("textbox", "searchbox") and any(
                k in keywords for k in ("search", "email", "user", "query", "type", "enter")
            ):
                score += 2.0
            if "login" in g or "sign" in g:
                if any(x in label for x in ("login", "sign in", "submit", "email", "password")):
                    score += 3.0
            if score <= 0:
                continue
            action = "click" if role in ("button", "link") or el.type == "button" else "fill"
            if role in ("textbox", "searchbox") or el.type in ("input", "textarea"):
                action = "fill"
            scored.append(
                (
                    score,
                    {
                        "action": action,
                        "element_id": el.id,
                        "role": el.role,
                        "label": (el.text or el.name or "")[:80],
                        "reason": f"keyword/role match score={score:.1f}",
                    },
                )
            )

        scored.sort(key=lambda x: (-x[0], x[1]["element_id"]))
        return [a for _, a in scored[:10]]

    def plan_structured(self, snapshot: Snapshot, goal: str) -> dict[str, Any]:
        return {
            "goal": goal,
            "page": {"title": snapshot.title, "url": snapshot.url},
            "steps_text": self.plan(snapshot, goal),
            "actions": self.suggest_actions(snapshot, goal),
        }
