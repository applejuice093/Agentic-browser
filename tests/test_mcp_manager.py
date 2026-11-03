"""MCP session manager unit tests (no stdio host required)."""

from __future__ import annotations

import pytest

from agent_browser.mcp.session_manager import McpSessionManager, _parse_allowlist


def test_parse_allowlist():
    assert _parse_allowlist("") == []
    assert _parse_allowlist("github.com, example.com") == ["github.com", "example.com"]


def test_allowlist_blocks_host():
    mgr = McpSessionManager(allowed_hosts=["github.com"])
    with pytest.raises(PermissionError):
        mgr.check_url_allowed("https://evil.example/phish")
    mgr.check_url_allowed("https://github.com/vercel/next.js")
    mgr.check_url_allowed("https://api.github.com/repos")


@pytest.mark.asyncio
async def test_manager_call_tool_observe_example():
    mgr = McpSessionManager(headless=True, max_tokens=1200, settle_budget_ms=5_000)
    try:
        result = await mgr.call_tool(
            "browser_navigate",
            {"url": "https://example.com", "detail": "sparse"},
        )
        assert result.get("ok") is True
        obs = await mgr.call_tool("browser_observe", {"detail": "sparse", "max_tokens": 800})
        assert "url" in obs or obs.get("ok") is not False
        # observe returns observation dict directly (to_llm_dict)
        assert "example" in str(obs.get("url", "")).lower() or "title" in obs
    finally:
        await mgr.stop()


async def test_create_mcp_server_registers_tools():
    """Every tool in TOOL_DEFINITIONS is exposed over MCP (mcp 1.x and 2.x)."""
    pytest.importorskip("mcp")
    from agent_browser.agent.tools import TOOL_DEFINITIONS
    from agent_browser.mcp.server import create_mcp_server

    server = create_mcp_server()
    registered = {tool.name for tool in await server.list_tools()}
    expected = {t.get("name") or t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert registered == expected


async def test_blocked_navigation_returns_structured_error():
    """Allowlist and URL problems come back as results, without starting a browser."""
    mgr = McpSessionManager(allowed_hosts=["github.com"])
    blocked = await mgr.call_tool("browser_navigate", {"url": "https://evil.example/"})
    assert blocked["ok"] is False
    assert blocked["error_code"] == "blocked"

    missing = await mgr.call_tool("browser_navigate", {})
    assert missing["error_code"] == "invalid_args"

    bad = await mgr.call_tool("browser_navigate", {"url": "not a url"})
    assert bad["error_code"] == "invalid_args"
    assert mgr._browser is None
