"""Key-value session memory backed by in-memory dict (SQLite in M7)."""

from __future__ import annotations

from typing import Any


class MemoryStore:
    """Per-session memory: form values, visited URLs, action history."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._kv: dict[str, Any] = {}
        self._actions: list[dict[str, Any]] = []
        self._urls: list[str] = []

    def set(self, key: str, value: Any) -> None:
        self._kv[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._kv.get(key, default)

    def log_action(self, action: dict[str, Any]) -> None:
        self._actions.append(action)

    def log_url(self, url: str) -> None:
        self._urls.append(url)

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "keys": list(self._kv.keys()),
            "action_count": len(self._actions),
            "urls": list(self._urls),
        }

    def clear(self) -> None:
        self._kv.clear()
        self._actions.clear()
        self._urls.clear()
