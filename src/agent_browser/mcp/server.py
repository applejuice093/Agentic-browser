"""
MCP server exposing agent-browser tools to Claude Desktop, Cursor, and other hosts.

Run:
  python -m agent_browser.mcp
  agent-browser-mcp

Tools map 1:1 to AgentSession.call_tool / TOOL_DEFINITIONS.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agent_browser.mcp.session_manager import get_manager

logger = logging.getLogger("agent_browser.mcp")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str, indent=2)


def create_mcp_server() -> Any:
    """Build a FastMCP server instance with all browser tools registered."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            "MCP SDK required. Install with: pip install 'agent-browser[mcp]' "
            "or pip install mcp"
        ) from exc

    mcp = FastMCP(
        "agent-browser",
        instructions=(
            "AI agent-first browser. Prefer compact observations over HTML. "
            "Use browser_observe after navigation. Check page_gate before acting. "
            "For GitHub tabs use browser_click_text with text=Issues scope=nav. "
            "ok=false with outcome_not_met means the action did not achieve intent."
        ),
    )
    manager = get_manager()

    async def _dispatch(name: str, **kwargs: Any) -> str:
        # Drop None values so defaults apply inside call_tool
        args = {k: v for k, v in kwargs.items() if v is not None}
        result = await manager.call_tool(name, args)
        return _json(result)

    @mcp.tool(name="browser_navigate")
    async def browser_navigate(url: str, detail: str = "normal") -> str:
        """Navigate to a URL. Returns ActionResult JSON with compact observation."""
        return await _dispatch("browser_navigate", url=url, detail=detail)

    @mcp.tool(name="browser_observe")
    async def browser_observe(
        detail: str = "normal",
        max_tokens: int = 2000,
        include_diff: bool = True,
    ) -> str:
        """Compact page observation (interactive refs, summary, page_gate). Prefer over HTML."""
        return await _dispatch(
            "browser_observe",
            detail=detail,
            max_tokens=max_tokens,
            include_diff=include_diff,
        )

    @mcp.tool(name="browser_click")
    async def browser_click(
        ref: int | None = None,
        text: str | None = None,
        scope: str = "nav",
        role: str = "link",
        intent: str | None = None,
        observe: bool = True,
    ) -> str:
        """Click by ref or by text (nav-scoped). Outcome-verified when intent implies navigation."""
        return await _dispatch(
            "browser_click",
            ref=ref,
            text=text,
            scope=scope,
            role=role,
            intent=intent,
            observe=observe,
        )

    @mcp.tool(name="browser_click_text")
    async def browser_click_text(
        text: str,
        scope: str = "nav",
        role: str = "link",
        intent: str | None = None,
        exact: bool = False,
        observe: bool = True,
    ) -> str:
        """Scoped text click with outcome verification (best for Issues/PRs tabs)."""
        return await _dispatch(
            "browser_click_text",
            text=text,
            scope=scope,
            role=role,
            intent=intent or text,
            exact=exact,
            observe=observe,
        )

    @mcp.tool(name="browser_type")
    async def browser_type(
        ref: int,
        text: str,
        clear: bool = True,
        submit: bool = False,
        observe: bool = True,
    ) -> str:
        """Type into element ref (clear first by default). Optionally press Enter."""
        return await _dispatch(
            "browser_type",
            ref=ref,
            text=text,
            clear=clear,
            submit=submit,
            observe=observe,
        )

    @mcp.tool(name="browser_wait")
    async def browser_wait(
        kind: str = "timeout",
        value: str | None = None,
        timeout_ms: float = 15_000,
    ) -> str:
        """Smart wait: timeout|selector|url|text|api|networkidle|load|domcontentloaded."""
        return await _dispatch(
            "browser_wait", kind=kind, value=value, timeout_ms=timeout_ms
        )

    @mcp.tool(name="browser_find")
    async def browser_find(
        role: str | None = None,
        name: str | None = None,
        text: str | None = None,
        exact: bool = False,
        scope: str = "any",
    ) -> str:
        """Find elements with scoped grounding. Use scope=nav for repo tabs."""
        return await _dispatch(
            "browser_find",
            role=role,
            name=name,
            text=text,
            exact=exact,
            scope=scope,
        )

    @mcp.tool(name="browser_network")
    async def browser_network(
        filter: str | None = None,  # noqa: A002
        graphql_only: bool = False,
    ) -> str:
        """List recent captured XHR/fetch API requests (summaries)."""
        return await _dispatch(
            "browser_network", filter=filter, graphql_only=graphql_only
        )

    @mcp.tool(name="browser_resync")
    async def browser_resync(detail: str = "normal") -> str:
        """Full resync when refs look stale (dismiss overlays + fresh observation)."""
        return await _dispatch("browser_resync", detail=detail)

    @mcp.tool(name="browser_prepare")
    async def browser_prepare() -> str:
        """Settle SPA and dismiss cookie/consent overlays."""
        return await _dispatch("browser_prepare")

    return mcp


def main() -> None:
    """CLI entry: stdio MCP server."""
    logging.basicConfig(level=logging.INFO)
    mcp = create_mcp_server()
    # FastMCP.run() defaults to stdio transport for host integration
    mcp.run()


if __name__ == "__main__":
    main()
