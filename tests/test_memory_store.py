"""SQLite-backed MemoryStore tests (no browser)."""

from __future__ import annotations

import gc

import pytest

from agent_browser.memory import MemoryStore


# An unclosed sqlite3.Connection emits ResourceWarning from __del__, which
# pytest reports as PytestUnraisableExceptionWarning; make that a failure.
@pytest.mark.filterwarnings("error::pytest.PytestUnraisableExceptionWarning")
@pytest.mark.filterwarnings("error::ResourceWarning")
def test_sqlite_connections_are_closed(tmp_path):
    mem = MemoryStore("s1", db_path=tmp_path / "mem.db")
    mem.set("k", {"v": 1})
    mem.log_url("https://example.com")
    mem.log_action({"type": "click", "ref": 3})
    mem.delete("k")
    mem.clear()
    gc.collect()


def test_reopened_session_restores_history(tmp_path):
    db = tmp_path / "mem.db"
    first = MemoryStore("s1", db_path=db)
    first.set("goal", "find docs")
    first.log_url("https://example.com/a")
    first.log_action({"type": "type", "field": "password", "value": "hunter2"})
    first.remember_form("login", {"user": "ana", "password": "hunter2"})

    again = MemoryStore("s1", db_path=db)
    assert again.get("goal") == "find docs"
    summary = again.memory_summary()
    assert summary["visited_urls"] == ["https://example.com/a"]
    assert summary["recent_actions"][0]["value"] == "***"
    assert summary["forms"] == {"login": {"user": "ana", "password": "***"}}

    other = MemoryStore("s2", db_path=db)
    assert other.actions() == [] and other.summary()["urls"] == []
