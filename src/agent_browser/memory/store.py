"""Session memory and history (M7) — in-memory with optional SQLite persist."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class MemoryStore:
    """
    Per-session memory: KV pairs, visited URLs, action history, form values.

    Sensitive keys (password, secret, token, …) are masked in history logs.
    """

    SENSITIVE_KEYWORDS = ("password", "passwd", "secret", "token", "api_key", "credit")

    def __init__(
        self,
        session_id: str | None = None,
        *,
        db_path: str | Path | None = None,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self._kv: dict[str, Any] = {}
        self._actions: list[dict[str, Any]] = []
        self._urls: list[dict[str, Any]] = []
        self._forms: dict[str, Any] = {}
        self._db_path = Path(db_path) if db_path else None
        if self._db_path:
            self._init_db()
            self._load_db()

    def _init_db(self) -> None:
        assert self._db_path is not None
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_kv (
                    session_id TEXT, key TEXT, value TEXT, ts REAL,
                    PRIMARY KEY (session_id, key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_actions (
                    session_id TEXT, ts REAL, action_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_urls (
                    session_id TEXT, ts REAL, url TEXT
                )
                """
            )

    def _load_db(self) -> None:
        assert self._db_path is not None
        with sqlite3.connect(self._db_path) as conn:
            for key, value in conn.execute(
                "SELECT key, value FROM memory_kv WHERE session_id=?",
                (self.session_id,),
            ):
                try:
                    self._kv[key] = json.loads(value)
                except json.JSONDecodeError:
                    self._kv[key] = value

    @staticmethod
    def _is_sensitive(key: str) -> bool:
        k = key.lower()
        return any(s in k for s in MemoryStore.SENSITIVE_KEYWORDS)

    @classmethod
    def mask_value(cls, key: str, value: Any) -> Any:
        if cls._is_sensitive(key):
            return "***"
        return value

    def set(self, key: str, value: Any) -> None:
        self._kv[key] = value
        if self._db_path:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO memory_kv(session_id, key, value, ts) VALUES (?,?,?,?)",
                    (self.session_id, key, json.dumps(value), time.time()),
                )

    def get(self, key: str, default: Any = None) -> Any:
        return self._kv.get(key, default)

    def delete(self, key: str) -> None:
        self._kv.pop(key, None)
        if self._db_path:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "DELETE FROM memory_kv WHERE session_id=? AND key=?",
                    (self.session_id, key),
                )

    def log_action(self, action: dict[str, Any]) -> None:
        safe = dict(action)
        if "value" in safe and isinstance(safe.get("target"), dict):
            t = safe["target"]
            key = str(t.get("name") or t.get("id") or "")
            if self._is_sensitive(key) or self._is_sensitive(str(safe.get("type", ""))):
                safe["value"] = "***"
        if "value" in safe and self._is_sensitive(str(safe.get("field", ""))):
            safe["value"] = "***"
        safe.setdefault("timestamp", time.time())
        self._actions.append(safe)
        if self._db_path:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO memory_actions(session_id, ts, action_json) VALUES (?,?,?)",
                    (self.session_id, safe["timestamp"], json.dumps(safe)),
                )

    def log_url(self, url: str) -> None:
        entry = {"url": url, "timestamp": time.time()}
        self._urls.append(entry)
        if self._db_path:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO memory_urls(session_id, ts, url) VALUES (?,?,?)",
                    (self.session_id, entry["timestamp"], url),
                )

    def remember_form(self, form_name: str, fields: dict[str, Any]) -> None:
        masked = {k: self.mask_value(k, v) for k, v in fields.items()}
        self._forms[form_name] = masked
        self.set(f"form:{form_name}", masked)

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "keys": list(self._kv.keys()),
            "action_count": len(self._actions),
            "urls": [u["url"] if isinstance(u, dict) else u for u in self._urls],
            "forms": list(self._forms.keys()),
        }

    def memory_summary(self, *, max_actions: int = 20) -> dict[str, Any]:
        """Agent-facing summary with masked secrets."""
        public_kv = {k: self.mask_value(k, v) for k, v in self._kv.items()}
        return {
            "session_id": self.session_id,
            "kv": public_kv,
            "recent_actions": self._actions[-max_actions:],
            "visited_urls": [u["url"] if isinstance(u, dict) else u for u in self._urls][-50:],
            "forms": self._forms,
        }

    def actions(self) -> list[dict[str, Any]]:
        return list(self._actions)

    def clear(self) -> None:
        self._kv.clear()
        self._actions.clear()
        self._urls.clear()
        self._forms.clear()
        if self._db_path:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("DELETE FROM memory_kv WHERE session_id=?", (self.session_id,))
                conn.execute("DELETE FROM memory_actions WHERE session_id=?", (self.session_id,))
                conn.execute("DELETE FROM memory_urls WHERE session_id=?", (self.session_id,))
