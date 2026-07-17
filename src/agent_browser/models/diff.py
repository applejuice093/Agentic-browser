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
