"""Event streaming models (M3)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Known browser event kinds."""

    NAVIGATION = "navigation"
    ELEMENT_ADDED = "element_added"
    ELEMENT_REMOVED = "element_removed"
    TEXT_CHANGED = "text_changed"
    ELEMENT_CLICKED = "element_clicked"
    API_CALL = "api_call"
    NETWORK_ERROR = "network_error"
    DIALOG_OPENED = "dialog_opened"
    DOWNLOAD_COMPLETE = "download_complete"
    PAGE_CHANGED = "page_changed"
    ERROR = "error"


class BrowserEvent(BaseModel):
    """JSON-serializable event pushed to agents."""

    event: EventType | str
    timestamp: float
    data: dict[str, Any] = Field(default_factory=dict)
