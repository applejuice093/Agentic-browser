"""Network intelligence and API discovery (M5)."""

from agent_browser.network.graphql import is_graphql_request, parse_graphql_payload
from agent_browser.network.monitor import NetworkMonitor

__all__ = [
    "NetworkMonitor",
    "is_graphql_request",
    "parse_graphql_payload",
]
