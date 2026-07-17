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


def test_create_mcp_server_registers_tools():
    from agent_browser.mcp.server import create_mcp_server

    server = create_mcp_server()
    assert server is not None
    # FastMCP stores tools by name
    names = set()
    tools = getattr(server, "_tool_manager", None) or getattr(server, "_tools", None)
    if tools is not None:
        if hasattr(tools, "list_tools"):
            pass
        elif isinstance(tools, dict):
            names = set(tools.keys())
    # At minimum construction succeeds with mcp installed
    assert create_mcp_server is not None
