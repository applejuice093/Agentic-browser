"""Stable element ID assignment across snapshots (M2)."""

from __future__ import annotations

import hashlib
import re
from typing import Any


_WS = re.compile(r"\s+")


def normalize_text(text: str | None, *, limit: int = 80) -> str:
    if not text:
        return ""
    return _WS.sub(" ", text).strip()[:limit]


def node_fingerprint(node: dict[str, Any]) -> str:
    """
    Build a stable fingerprint for a semantic node.

    Prefers durable identity (html id, name, role) over layout position so
    minor reflows do not churn IDs. Includes a structural path as a tie-breaker.
    """
    tag = (node.get("type") or node.get("tag") or "").lower()
    attrs = node.get("attributes") or {}
    html_id = attrs.get("id") or ""
    name_attr = attrs.get("name") or ""
    role = (node.get("role") or "").lower()
    name = normalize_text(node.get("name"))
    text = normalize_text(node.get("text"))
    path = node.get("dom_path") or node.get("path") or ""
    # If the node has a unique html id, that alone is enough for identity.
    if html_id:
        key = f"id:{html_id}|{tag}|{role}"
    elif name_attr:
        key = f"name:{name_attr}|{tag}|{role}|{text}"
    else:
        key = f"{tag}|{role}|{name}|{text}|{path}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def secondary_keys(node: dict[str, Any]) -> list[str]:
    """Weaker keys used for fuzzy rebinding when primary fingerprint misses."""
    tag = (node.get("type") or "").lower()
    attrs = node.get("attributes") or {}
    role = (node.get("role") or "").lower()
    text = normalize_text(node.get("text"))
    name = normalize_text(node.get("name"))
    keys: list[str] = []
    if attrs.get("id"):
        keys.append(f"htmlid:{attrs['id']}")
    if attrs.get("name"):
        keys.append(f"attrname:{tag}:{attrs['name']}")
    if name:
        keys.append(f"accname:{role}:{name}")
    if text:
        keys.append(f"text:{tag}:{role}:{text}")
    path = node.get("dom_path") or ""
    if path:
        keys.append(f"path:{path}")
    return keys


class StableIDAssigner:
    """
    Maps node fingerprints to persistent integer IDs for a page session.

    On each snapshot, nodes that match prior fingerprints (or secondary keys)
    reuse the same id. Removed nodes free their secondary keys but IDs are never
    reused within a session (monotonic counter).
    """

    def __init__(self) -> None:
        self._next_id = 1
        self._fingerprint_to_id: dict[str, int] = {}
        self._id_to_fingerprint: dict[int, str] = {}
        self._secondary_to_id: dict[str, int] = {}

    def reset(self) -> None:
        """Clear all mappings (call on full navigation)."""
        self._next_id = 1
        self._fingerprint_to_id.clear()
        self._id_to_fingerprint.clear()
        self._secondary_to_id.clear()

    def assign(self, fingerprint: str) -> int:
        if fingerprint in self._fingerprint_to_id:
            return self._fingerprint_to_id[fingerprint]
        eid = self._next_id
        self._next_id += 1
        self._fingerprint_to_id[fingerprint] = eid
        self._id_to_fingerprint[eid] = fingerprint
        return eid

    def assign_nodes(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Assign stable ids to a list of raw node dicts (mutates copies).

        Returns new dicts with ``id`` and ``fingerprint`` set.
        """
        # Build reverse lookup of currently live secondary keys from previous pass
        used_ids: set[int] = set()
        result: list[dict[str, Any]] = []

        for node in nodes:
            raw = dict(node)
            fp = node_fingerprint(raw)
            eid: int | None = self._fingerprint_to_id.get(fp)

            if eid is None:
                # Try secondary keys from previous snapshot
                for sk in secondary_keys(raw):
                    candidate = self._secondary_to_id.get(sk)
                    if candidate is not None and candidate not in used_ids:
                        eid = candidate
                        # Rebind primary fingerprint to this id
                        old_fp = self._id_to_fingerprint.get(eid)
                        if old_fp and old_fp in self._fingerprint_to_id:
                            del self._fingerprint_to_id[old_fp]
                        self._fingerprint_to_id[fp] = eid
                        self._id_to_fingerprint[eid] = fp
                        break

            if eid is None:
                eid = self.assign(fp)
            else:
                used_ids.add(eid)

            used_ids.add(eid)
            raw["id"] = eid
            raw["fingerprint"] = fp
            result.append(raw)

        # Rebuild secondary index only from live nodes
        self._secondary_to_id.clear()
        for raw in result:
            eid = int(raw["id"])
            for sk in secondary_keys(raw):
                # First writer wins so duplicates don't steal ids
                self._secondary_to_id.setdefault(sk, eid)

        return result

    def rebind(
        self,
        old_map: dict[str, int],
        new_nodes: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Compatibility helper: seed from old_map then assign_nodes."""
        for fp, eid in old_map.items():
            self._fingerprint_to_id[fp] = eid
            self._id_to_fingerprint[eid] = fp
            if eid >= self._next_id:
                self._next_id = eid + 1
        assigned = self.assign_nodes(new_nodes)
        return {str(n["fingerprint"]): int(n["id"]) for n in assigned}
