"""Page snapshot returned to agents."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent_browser.models.element import Element


class Snapshot(BaseModel):
    """
    Compressed semantic view of a page.

    Full semantic tree + metadata; later milestones add alerts, dialogs, diffs.
    """

    url: str
    title: str = ""
    scroll_position: float = 0.0
    elements: list[Element] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    dialogs: list[dict[str, str]] = Field(default_factory=list)
    raw_html: str | None = None  # M1: optional raw dump; prefer elements later
