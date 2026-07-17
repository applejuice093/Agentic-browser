"""Event streaming models (M3)."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Known browser event kinds."""

    NAVIGATION = "navigation"
    ELEMENT_ADDED = "element_added"
    ELEMENT_REMOVED = "element_removed"
    TEXT_CHANGED = "text_changed"
    VALUE_CHANGED = "value_changed"
    ELEMENT_CLICKED = "element_clicked"
    ELEMENT_TYPED = "element_typed"
    ELEMENT_FILLED = "element_filled"
    API_CALL = "api_call"
    NETWORK_ERROR = "network_error"
    DIALOG_OPENED = "dialog_opened"
    DOWNLOAD_COMPLETE = "download_complete"
    PAGE_CHANGED = "page_changed"
    MUTATION = "mutation"
    SNAPSHOT = "snapshot"
    ERROR = "error"


class BrowserEvent(BaseModel):
    """JSON-serializable event pushed to agents."""

    event: EventType | str
    timestamp: float = Field(default_factory=time.time)
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def make(cls, event: EventType | str, **data: Any) -> BrowserEvent:
        return cls(event=event, timestamp=time.time(), data=data)
