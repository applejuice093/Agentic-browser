"""Compact observation builders for LLM agents.

Public helpers used by AgentSession and MCP tools to turn snapshots into
token-budgeted Observation payloads.
"""

from agent_browser.observation.compact import (
    build_observation,
    element_to_ref,
    is_heading,
    is_interactive,
    is_landmark,
)

__all__ = [
    "build_observation",
    "element_to_ref",
    "is_heading",
    "is_interactive",
    "is_landmark",
]
