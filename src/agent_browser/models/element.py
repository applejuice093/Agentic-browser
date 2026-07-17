"""Semantic element model (stable IDs, roles, attributes)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Screen coordinates of an element."""

    x: float
    y: float
    width: float
    height: float


class Element(BaseModel):
    """
    High-level page object exposed to agents.

    Matches the semantic DOM schema from the design report:
    stable int id, ARIA role, HTML type, text, visibility, etc.
    """

    id: int
    role: str | None = None
    type: str | None = None
    text: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    value: str | None = None
    checked: bool | None = None
    visible: bool = True
    enabled: bool = True
    bounding_box: BoundingBox | None = None
    parent_id: int | None = None
    children_ids: list[int] = Field(default_factory=list)
    confidence: float | None = None
    name: str | None = None
    description: str | None = None
