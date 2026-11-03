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
