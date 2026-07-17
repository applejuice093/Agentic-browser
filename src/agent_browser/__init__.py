"""
Agent Browser — AI agent-first browser API.

Exposes the web as a continuous semantic world model for LLM agents:
stable refs, compact observations, action results, diffs, network, and tools.
"""

from agent_browser.agent import (
    TOOL_DEFINITIONS,
    AgentSession,
    tool_names,
    tools_as_anthropic,
    tools_as_openai,
)
from agent_browser.browser import Browser
from agent_browser.config import BrowserConfig
from agent_browser.events import DiffEngine, EventBus
from agent_browser.exceptions import (
    AgentBrowserError,
    BrowserNotStartedError,
    ElementNotFoundError,
    NavigationError,
    NetworkTimeoutError,
    SnapshotError,
    VisionError,
)
from agent_browser.memory import MemoryStore
from agent_browser.models.diff import Diff
from agent_browser.models.element import BoundingBox, Element
from agent_browser.models.events import BrowserEvent, EventType
from agent_browser.models.network import NetworkRequest
from agent_browser.models.observation import (
    ActionResult,
    DetailLevel,
    ErrorCode,
    InteractiveRef,
    Observation,
)
from agent_browser.models.snapshot import Snapshot
from agent_browser.models.vision import OCRRegion, VisionDetection, VisionResult
from agent_browser.multiagent import AgentHandle, MultiAgentSession
from agent_browser.network import NetworkMonitor
from agent_browser.page import Page
from agent_browser.planning import ContextBuilder, Planner
from agent_browser.scrape import scrape_page, scrape_url, snapshot_to_scrape_result
from agent_browser.semantic import SemanticDOMEngine, StableIDAssigner
from agent_browser.vision import OCREngine, UIDetector, VisionDependencyError, VisionEngine

__version__ = "0.4.0"

__all__ = [
    "Browser",
    "Page",
    "AgentSession",
    "Observation",
    "ActionResult",
    "InteractiveRef",
    "DetailLevel",
    "ErrorCode",
    "TOOL_DEFINITIONS",
    "tools_as_openai",
    "tools_as_anthropic",
    "tool_names",
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
    "NetworkMonitor",
    "NetworkRequest",
    "scrape_page",
    "scrape_url",
    "snapshot_to_scrape_result",
    "MemoryStore",
    "ContextBuilder",
    "Planner",
    "MultiAgentSession",
    "AgentHandle",
    "AgentBrowserError",
    "BrowserNotStartedError",
    "ElementNotFoundError",
    "NavigationError",
    "NetworkTimeoutError",
    "SnapshotError",
    "__version__",
]
