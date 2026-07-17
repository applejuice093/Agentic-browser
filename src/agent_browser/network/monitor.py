"""XHR/Fetch/WebSocket capture and wait_for_api (M5)."""

from __future__ import annotations

from typing import Any


class NetworkMonitor:
    """Hooks Playwright network events for agent introspection."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    async def attach(self, page: Any) -> None:
        raise NotImplementedError("NetworkMonitor.attach is implemented in M5")

    async def wait_for_api(self, url_pattern: str, *, timeout_ms: int = 30_000) -> dict[str, Any]:
        raise NotImplementedError("NetworkMonitor.wait_for_api is implemented in M5")

    def list_requests(self, *, filter: str | None = None) -> list[dict[str, Any]]:  # noqa: A002
        if filter is None:
            return list(self.requests)
        return [r for r in self.requests if filter in str(r.get("url", ""))]
