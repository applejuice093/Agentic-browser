"""
Shared browser + AgentSession for MCP / long-lived tool hosts.

One browser context per MCP process by default (simple, predictable).
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlparse

from agent_browser.agent.session import AgentSession
from agent_browser.browser import Browser
from agent_browser.config import BrowserConfig


class McpSessionManager:
    """Lazy-start Browser and AgentSession for tool dispatch."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        max_tokens: int = 2000,
        detail: str = "normal",
        settle_budget_ms: float = 8_000,
        allowed_hosts: list[str] | None = None,
    ) -> None:
        if headless is None:
            headless = os.environ.get("AGENT_BROWSER_HEADLESS", "true").lower() in (
                "1",
                "true",
                "yes",
            )
        self.headless = headless
        self.max_tokens = int(os.environ.get("AGENT_BROWSER_MAX_TOKENS", str(max_tokens)))
        self.detail = os.environ.get("AGENT_BROWSER_DETAIL", detail)
        self.settle_budget_ms = float(
            os.environ.get("AGENT_BROWSER_SETTLE_MS", str(settle_budget_ms))
        )
        allow = allowed_hosts or _parse_allowlist(
            os.environ.get("AGENT_BROWSER_ALLOWED_HOSTS", "")
        )
        self.allowed_hosts = [h.lower().lstrip(".") for h in allow if h]

        self._browser: Browser | None = None
        self._agent: AgentSession | None = None
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            cfg = BrowserConfig(
                headless=self.headless,
                default_timeout_ms=int(
                    os.environ.get("AGENT_BROWSER_DEFAULT_TIMEOUT_MS", "30000")
                ),
            )
            self._browser = Browser(config=cfg)
            await self._browser.start()
            page = await self._browser.new_page()
            self._agent = page.as_agent(
                detail=self.detail,
                max_tokens=self.max_tokens,
                settle_budget_ms=self.settle_budget_ms,
            )
            self._started = True

    async def stop(self) -> None:
        async with self._lock:
            if self._browser is not None:
                try:
                    await self._browser.stop()
                except Exception:
                    pass
            self._browser = None
            self._agent = None
            self._started = False

    async def ensure_agent(self) -> AgentSession:
        if not self._started or self._agent is None:
            await self.start()
        assert self._agent is not None
        return self._agent

    def check_url_allowed(self, url: str) -> None:
        if not self.allowed_hosts:
            return
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception as exc:
            raise ValueError(f"invalid url: {url}") from exc
        if not host:
            raise ValueError(f"invalid url host: {url}")
        for allowed in self.allowed_hosts:
            if host == allowed or host.endswith("." + allowed):
                return
        raise PermissionError(
            f"host {host!r} not in AGENT_BROWSER_ALLOWED_HOSTS={self.allowed_hosts}"
        )

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = dict(arguments or {})
        if name in ("browser_navigate",) and "url" in args:
            self.check_url_allowed(str(args["url"]))
        agent = await self.ensure_agent()
        # First navigation via open if agent page is blank
        if name == "browser_navigate" and self._browser is not None:
            url = str(args.get("url", ""))
            if url and (
                not agent.page.url
                or agent.page.url in ("about:blank", "chrome://newtab/")
            ):
                # use agent.navigate which uses page.goto
                pass
        try:
            result = await agent.call_tool(name, args)
            if not isinstance(result, dict):
                return {"ok": True, "result": result}
            return result
        except PermissionError as exc:
            return {
                "ok": False,
                "error_code": "blocked",
                "error_message": str(exc),
            }
        except Exception as exc:
            return {
                "ok": False,
                "error_code": "unknown",
                "error_message": f"{type(exc).__name__}: {exc}",
            }


def _parse_allowlist(raw: str) -> list[str]:
    if not raw.strip():
        return []
    return [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]


# Process-global manager for MCP stdio server
_MANAGER: McpSessionManager | None = None


def get_manager() -> McpSessionManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = McpSessionManager()
    return _MANAGER
