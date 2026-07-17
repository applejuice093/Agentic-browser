"""Semantic DOM engine (M2): object model, tree cleanup, stable IDs."""

from agent_browser.semantic.engine import SemanticDOMEngine
from agent_browser.semantic.ids import StableIDAssigner, node_fingerprint

__all__ = ["SemanticDOMEngine", "StableIDAssigner", "node_fingerprint"]
