"""Public exceptions for the agent browser API."""

from __future__ import annotations


class AgentBrowserError(Exception):
    """Base error for agent-browser."""


class BrowserNotStartedError(AgentBrowserError):
    """Raised when an operation requires a started browser session."""


class BrowserAlreadyStartedError(AgentBrowserError):
    """Raised when start() is called on an already-started browser (strict mode)."""


class ElementNotFoundError(AgentBrowserError):
    """Raised when a click/type target cannot be resolved."""


class NavigationError(AgentBrowserError):
    """Raised when navigation fails or times out."""


class SnapshotError(AgentBrowserError):
    """Raised when a page snapshot cannot be captured."""


class TimeoutError(AgentBrowserError):
    """Raised when an operation exceeds the configured timeout."""


class VisionError(AgentBrowserError):
    """Raised when OCR/vision fails or dependencies are missing."""


class NetworkTimeoutError(TimeoutError):
    """Raised when wait_for_api exceeds its timeout."""
