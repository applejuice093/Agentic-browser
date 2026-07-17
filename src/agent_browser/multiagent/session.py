"""Shared browser sessions for multiple cooperating agents (M9)."""

from __future__ import annotations

from typing import Any


class MultiAgentSession:
    """Coordinate multiple agents on isolated or shared sessions."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.agents: dict[str, Any] = {}

    def attach(self, agent_id: str, handle: Any) -> None:
        self.agents[agent_id] = handle

    def detach(self, agent_id: str) -> None:
        self.agents.pop(agent_id, None)

    def list_agents(self) -> list[str]:
        return list(self.agents.keys())
