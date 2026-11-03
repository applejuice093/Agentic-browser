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
from agent_browser.models.observation import DetailLevel, ErrorCode


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
            headless = os.environ.get("AGENT_BROWSER_HEADLESS", "true").strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
        self.headless = headless
        self.max_tokens = int(_env_number("AGENT_BROWSER_MAX_TOKENS", max_tokens, minimum=1))
        self.detail = os.environ.get("AGENT_BROWSER_DETAIL", detail).strip().lower()
        if self.detail not in _DETAIL_LEVELS:
            raise ValueError(
                f"AGENT_BROWSER_DETAIL must be one of {', '.join(_DETAIL_LEVELS)}, "
                f"got {self.detail!r}"
            )
        self.settle_budget_ms = _env_number("AGENT_BROWSER_SETTLE_MS", settle_budget_ms)
        allow = allowed_hosts or _parse_allowlist(
            os.environ.get("AGENT_BROWSER_ALLOWED_HOSTS", "")
        )
        self.allowed_hosts = [h for h in (_normalize_host(a) for a in allow) if h]

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
        """Raise unless ``url`` is an http(s) URL on an allowed host.

        With an allowlist set, other schemes are refused too: otherwise
        ``file://github.com/etc/passwd`` would pass the host check.
        """
        if not self.allowed_hosts:
            return
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower().rstrip(".")
        except Exception as exc:
            raise ValueError(f"invalid url: {url}") from exc
        if not host:
            raise ValueError(f"invalid url host: {url}")
        if parsed.scheme.lower() not in ("http", "https"):
            raise PermissionError(
                f"scheme {parsed.scheme!r} not allowed while AGENT_BROWSER_ALLOWED_HOSTS is set"
            )
        for allowed in self.allowed_hosts:
            if host == allowed or host.endswith("." + allowed):
                return
        raise PermissionError(
            f"host {host!r} not in AGENT_BROWSER_ALLOWED_HOSTS={self.allowed_hosts}"
        )

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = dict(arguments or {})
        # Validate the URL before starting a browser, and report problems as a
        # structured result rather than letting the exception reach the host.
        if name == "browser_navigate":
            if not str(args.get("url") or "").strip():
                return _error(ErrorCode.INVALID_ARGS, "browser_navigate requires a url")
            try:
                self.check_url_allowed(str(args["url"]))
            except PermissionError as exc:
                return _error(ErrorCode.BLOCKED, str(exc))
            except ValueError as exc:
                return _error(ErrorCode.INVALID_ARGS, str(exc))
        try:
            agent = await self.ensure_agent()
            result = await agent.call_tool(name, args)
            if not isinstance(result, dict):
                return {"ok": True, "result": result}
            return result
        except PermissionError as exc:
            return _error(ErrorCode.BLOCKED, str(exc))
        except Exception as exc:
            return _error(ErrorCode.UNKNOWN, f"{type(exc).__name__}: {exc}")


def _error(code: ErrorCode, message: str) -> dict[str, Any]:
    return {"ok": False, "error_code": code.value, "error_message": message}


_DETAIL_LEVELS = tuple(level.value for level in DetailLevel)


def _env_number(name: str, default: float, *, minimum: float = 0) -> float:
    """Read a numeric env var, naming the variable if the value is unusable.

    A bare int()/float() failure ("invalid literal for int()") gave no hint
    which setting was wrong when the MCP server started.
    """
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return float(default)
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum:g}, got {raw!r}")
    return value


def _normalize_host(entry: str) -> str:
    """Reduce an allowlist entry to a bare lowercase hostname.

    Accepts forms people naturally paste, e.g. ``https://GitHub.com/``,
    ``github.com:443`` or ``.github.com``, which would otherwise never match.
    """
    value = entry.strip().lower()
    if "://" in value:
        value = urlparse(value).hostname or ""
    value = value.split("/", 1)[0].split(":", 1)[0]
    return value.strip(".")


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
