"""Semantic DOM builder — implemented in milestone M2."""

from __future__ import annotations

from typing import Any

from agent_browser.models.element import Element
from agent_browser.models.snapshot import Snapshot


class SemanticDOMEngine:
    """
    Merges HTML, CSS, ARIA, and optional vision into a semantic tree.

    Placeholder for M2; M1 uses Page._extract_basic_elements instead.
    """

    def __init__(self) -> None:
        self._elements: dict[int, Element] = {}

    def build(self, raw_dom: Any, ax_tree: Any | None = None) -> Snapshot:
        raise NotImplementedError("SemanticDOMEngine.build is implemented in M2")

    def query(
        self,
        *,
        role: str | None = None,
        text_contains: str | None = None,
        name: str | None = None,
    ) -> list[Element]:
        raise NotImplementedError("SemanticDOMEngine.query is implemented in M2")
