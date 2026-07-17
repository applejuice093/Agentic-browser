"""Accessibility / ARIA engine and queries (M2/M6)."""

from agent_browser.accessibility.engine import AccessibilityEngine
from agent_browser.accessibility.queries import (
    filter_by_label,
    filter_by_placeholder,
    filter_by_role,
    filter_by_test_id,
    filter_by_text,
)

__all__ = [
    "AccessibilityEngine",
    "filter_by_role",
    "filter_by_label",
    "filter_by_placeholder",
    "filter_by_text",
    "filter_by_test_id",
]
