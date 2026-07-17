"""
Agent Browser — AI agent-first browser API.

Exposes the web as a semantic world model for LLM agents:
stable element IDs, accessibility-aware snapshots, diffs, and high-level actions.
"""

from agent_browser.browser import Browser
from agent_browser.config import BrowserConfig
from agent_browser.events import DiffEngine, EventBus
from agent_browser.exceptions import (
    AgentBrowserError,
    BrowserNotStartedError,
    ElementNotFoundError,
    NavigationError,
    SnapshotError,
    VisionError,
)
from agent_browser.models.diff import Diff
from agent_browser.models.element import BoundingBox, Element
from agent_browser.models.events import BrowserEvent, EventType
from agent_browser.models.snapshot import Snapshot
from agent_browser.models.vision import OCRRegion, VisionDetection, VisionResult
from agent_browser.page import Page
from agent_browser.semantic import SemanticDOMEngine, StableIDAssigner
from agent_browser.vision import OCREngine, UIDetector, VisionDependencyError, VisionEngine

__version__ = "0.1.0"

__all__ = [
    "Browser",
    "Page",
    "Element",
    "BoundingBox",
    "Snapshot",
    "Diff",
    "BrowserEvent",
    "EventType",
    "EventBus",
    "DiffEngine",
    "BrowserConfig",
    "SemanticDOMEngine",
    "StableIDAssigner",
    "OCREngine",
    "UIDetector",
    "VisionEngine",
    "OCRRegion",
    "VisionDetection",
    "VisionResult",
    "VisionDependencyError",
    "VisionError",
    "AgentBrowserError",
    "BrowserNotStartedError",
    "ElementNotFoundError",
    "NavigationError",
    "SnapshotError",
    "__version__",
]
