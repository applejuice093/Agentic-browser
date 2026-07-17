"""AX tree extraction and merge (M2/M6)."""

from __future__ import annotations

from typing import Any


class AccessibilityEngine:
    """Builds and merges the browser accessibility tree into semantic objects."""

    async def snapshot(self, page: Any) -> dict[str, Any]:
        """Return Playwright/CDP accessibility snapshot — M2."""
        raise NotImplementedError("AccessibilityEngine.snapshot is implemented in M2/M6")

    def merge_into_elements(self, elements: list[Any], ax_tree: dict[str, Any]) -> list[Any]:
        raise NotImplementedError("AccessibilityEngine.merge_into_elements is implemented in M6")
