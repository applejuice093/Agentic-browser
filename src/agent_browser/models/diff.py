"""Incremental DOM / semantic tree diffs (M3)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_browser.models.element import Element


class Diff(BaseModel):
    """Changes between two semantic snapshots."""

    added: list[Element] = Field(default_factory=list)
    removed: list[int] = Field(default_factory=list)
    changed: list[dict[str, Any]] = Field(default_factory=list)
    url_changed: bool = False
    previous_url: str | None = None
    current_url: str | None = None
    title_changed: bool = False

    @property
    def is_empty(self) -> bool:
        return (
            not self.added
            and not self.removed
            and not self.changed
            and not self.url_changed
            and not self.title_changed
        )

    def summary(self) -> dict[str, Any]:
        return {
            "added": len(self.added),
            "removed": len(self.removed),
            "changed": len(self.changed),
            "url_changed": self.url_changed,
            "title_changed": self.title_changed,
            "is_empty": self.is_empty,
        }
