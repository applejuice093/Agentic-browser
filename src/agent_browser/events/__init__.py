"""Event bus, diffs, and mutation monitoring (M3)."""

from agent_browser.events.bus import EventBus
from agent_browser.events.diffing import DiffEngine
from agent_browser.events.monitor import MutationMonitor

__all__ = ["EventBus", "DiffEngine", "MutationMonitor"]
