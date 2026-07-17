"""Stable element ID assignment across snapshots (M2)."""

from __future__ import annotations

from typing import Any


class StableIDAssigner:
    """Maps DOM node fingerprints to persistent integer IDs for a session."""

    def __init__(self) -> None:
        self._next_id = 1
        self._fingerprint_to_id: dict[str, int] = {}

    def assign(self, fingerprint: str) -> int:
        if fingerprint in self._fingerprint_to_id:
            return self._fingerprint_to_id[fingerprint]
        eid = self._next_id
        self._next_id += 1
        self._fingerprint_to_id[fingerprint] = eid
        return eid

    def rebind(self, old_map: dict[str, int], new_nodes: list[dict[str, Any]]) -> dict[str, int]:
        """Match new nodes to previous IDs — full matching lands in M2."""
        raise NotImplementedError("StableIDAssigner.rebind is implemented in M2")
