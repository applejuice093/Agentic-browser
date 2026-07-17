"""
Page settle strategy: fast, budgeted waits for SPAs without hanging forever.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from agent_browser.page import Page


async def settle_page(
    page: Page,
    *,
    budget_ms: float = 8_000,
    wait_networkidle: bool = True,
    networkidle_ms: float = 2_500,
    extra_ms: float = 400,
    dismiss_overlays: bool = True,
    scroll_probe: bool = False,
) -> dict[str, Any]:
    """
    Bring the page to a usable state within ``budget_ms``.

    Order:
      1. domcontentloaded (short)
      2. optional networkidle with cap
      3. dismiss overlays
      4. optional light scroll to trigger lazy content
      5. small extra paint delay
    """
    from agent_browser.agent.overlays import dismiss_overlays as _dismiss

    t0 = time.perf_counter()
    steps: list[str] = []
    deadline = t0 + budget_ms / 1000.0

    async def remaining_ms() -> float:
        return max(0.0, (deadline - time.perf_counter()) * 1000)

    # DOM ready
    try:
        await asyncio.wait_for(
            page.wait_for_load_state("domcontentloaded"),
            timeout=min(3.0, budget_ms / 1000.0),
        )
        steps.append("domcontentloaded")
    except Exception:
        steps.append("domcontentloaded_skip")

    # Network idle capped
    if wait_networkidle and await remaining_ms() > 500:
        try:
            await asyncio.wait_for(
                page.wait_for_load_state("networkidle"),
                timeout=min(networkidle_ms, await remaining_ms()) / 1000.0,
            )
            steps.append("networkidle")
        except Exception:
            steps.append("networkidle_timeout")

    overlay_stats: dict[str, Any] = {}
    if dismiss_overlays and await remaining_ms() > 200:
        try:
            overlay_stats = await _dismiss(page)
            if overlay_stats.get("clicked") or overlay_stats.get("hidden_nodes"):
                steps.append("overlays_dismissed")
        except Exception as exc:
            overlay_stats = {"error": str(exc)}
            steps.append("overlays_error")

    if scroll_probe and await remaining_ms() > 300:
        try:
            await page.evaluate(
                """async () => {
                  const h = Math.min(document.body.scrollHeight, 3000);
                  const steps = 3;
                  for (let i = 1; i <= steps; i++) {
                    window.scrollTo(0, (h * i) / steps);
                    await new Promise(r => setTimeout(r, 120));
                  }
                  window.scrollTo(0, 0);
                }"""
            )
            steps.append("scroll_probe")
        except Exception:
            steps.append("scroll_probe_skip")

    # paint cushion
    cushion = min(extra_ms, await remaining_ms())
    if cushion > 50:
        await asyncio.sleep(cushion / 1000.0)
        steps.append(f"paint_{int(cushion)}ms")

    return {
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "steps": steps,
        "overlays": overlay_stats,
    }
