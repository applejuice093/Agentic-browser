"""MutationObserver bridge for live DOM change notifications (M3)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from agent_browser.models.events import BrowserEvent, EventType

# Injected into the page. Batches mutations and calls the exposed binding.
MUTATION_OBSERVER_JS = r"""
(debounceMs) => {
  if (window.__agentBrowserMO) {
    return { already: true };
  }
  let timer = null;
  let batch = { childList: 0, attributes: 0, characterData: 0 };
  const flush = () => {
    timer = null;
    const payload = {
      childList: batch.childList,
      attributes: batch.attributes,
      characterData: batch.characterData,
      ts: Date.now(),
    };
    batch = { childList: 0, attributes: 0, characterData: 0 };
    if (window.__agentBrowserNotify) {
      window.__agentBrowserNotify(payload);
    }
  };
  const mo = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === 'childList') batch.childList += 1;
      else if (m.type === 'attributes') {
        // ignore our own stamps
        if (m.attributeName === 'data-agent-id') continue;
        batch.attributes += 1;
      } else if (m.type === 'characterData') batch.characterData += 1;
    }
    if (batch.childList || batch.attributes || batch.characterData) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(flush, debounceMs);
    }
  });
  const root = document.documentElement || document.body;
  if (root) {
    mo.observe(root, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
    });
  }
  window.__agentBrowserMO = mo;
  window.__agentBrowserMOTimer = () => timer;
  return { ok: true };
}
"""

MUTATION_OBSERVER_STOP_JS = r"""
() => {
  if (window.__agentBrowserMO) {
    window.__agentBrowserMO.disconnect();
    delete window.__agentBrowserMO;
  }
  return true;
}
"""


OnMutation = Callable[[dict[str, Any]], Awaitable[None] | None]


class MutationMonitor:
    """
    Installs a MutationObserver in-page and forwards batched mutations
    to Python via ``page.expose_binding``.
    """

    def __init__(
        self,
        *,
        debounce_ms: int = 100,
        on_mutation: OnMutation | None = None,
    ) -> None:
        self.debounce_ms = debounce_ms
        self._on_mutation = on_mutation
        self._attached = False
        self._page: Any = None
        self._binding_name = "__agentBrowserNotify"
        self._last_mutation_at: float | None = None
        self._pending_task: asyncio.Task[None] | None = None

    @property
    def is_attached(self) -> bool:
        return self._attached

    @property
    def last_mutation_at(self) -> float | None:
        return self._last_mutation_at

    async def attach(self, page: Any, on_mutation: OnMutation | None = None) -> None:
        if self._attached:
            return
        if on_mutation is not None:
            self._on_mutation = on_mutation
        self._page = page

        async def _binding(source: Any, payload: dict[str, Any]) -> None:  # noqa: ARG001
            self._last_mutation_at = time.time()
            if self._on_mutation is not None:
                result = self._on_mutation(payload)
                if asyncio.iscoroutine(result):
                    await result

        # expose_binding may fail if re-attached with same name on same page
        try:
            await page.expose_binding(self._binding_name, _binding)
        except Exception:
            # Binding may already exist after soft re-attach; continue inject
            pass

        await page.evaluate(MUTATION_OBSERVER_JS, self.debounce_ms)
        self._attached = True

    async def detach(self) -> None:
        if not self._attached or self._page is None:
            self._attached = False
            return
        try:
            await self._page.evaluate(MUTATION_OBSERVER_STOP_JS)
        except Exception:
            pass
        self._attached = False
        self._page = None

    def mutation_event(self, payload: dict[str, Any]) -> BrowserEvent:
        return BrowserEvent.make(EventType.MUTATION, **payload)
