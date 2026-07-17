"""
JSON tool definitions for binding this browser to an LLM tool-caller.

Compatible in spirit with OpenAI tools / MCP input schemas.
"""

from __future__ import annotations

from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "browser_navigate",
        "description": "Navigate the page to a URL. Returns ActionResult with compact observation.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Absolute URL to open"},
                "detail": {
                    "type": "string",
                    "enum": ["sparse", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser_observe",
        "description": (
            "Capture a compact observation of the current page (interactive refs, "
            "optional diff vs last step). Prefer this over full HTML."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "detail": {
                    "type": "string",
                    "enum": ["sparse", "normal", "full"],
                    "default": "normal",
                },
                "max_tokens": {"type": "integer", "default": 2000},
                "include_diff": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "browser_click",
        "description": (
            "Click by ref OR by text. Prefer text+scope=nav for tabs (Issues, PRs). "
            "Success requires outcome verification when intent implies navigation "
            "(e.g. Issues → URL must contain /issues). ok=false if outcome not met."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "integer", "description": "Stable element ref"},
                "text": {
                    "type": "string",
                    "description": "Visible label to ground (use with scope=nav for repo tabs)",
                },
                "scope": {
                    "type": "string",
                    "enum": ["any", "nav", "main", "form"],
                    "default": "nav",
                },
                "role": {"type": "string", "default": "link"},
                "intent": {
                    "type": "string",
                    "description": "Natural intent for outcome checks, e.g. 'open issues'",
                },
                "observe": {
                    "type": "boolean",
                    "default": True,
                    "description": "Return post-action observation",
                },
            },
        },
    },
    {
        "name": "browser_click_text",
        "description": "Scoped text click with outcome verification (nav-first grounding).",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "scope": {
                    "type": "string",
                    "enum": ["any", "nav", "main", "form"],
                    "default": "nav",
                },
                "role": {"type": "string", "default": "link"},
                "intent": {"type": "string"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "browser_type",
        "description": "Type text into an element ref (clears first if clear=true).",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "integer"},
                "text": {"type": "string"},
                "clear": {"type": "boolean", "default": True},
                "submit": {
                    "type": "boolean",
                    "default": False,
                    "description": "Press Enter after typing",
                },
                "observe": {"type": "boolean", "default": True},
            },
            "required": ["ref", "text"],
        },
    },
    {
        "name": "browser_wait",
        "description": "Smart wait: timeout|selector|url|text|api|networkidle|load.",
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": [
                        "timeout",
                        "selector",
                        "url",
                        "text",
                        "api",
                        "networkidle",
                        "load",
                        "domcontentloaded",
                    ],
                },
                "value": {
                    "type": "string",
                    "description": "selector / url pattern / text / api pattern / ms for timeout",
                },
                "timeout_ms": {"type": "number", "default": 15000},
            },
            "required": ["kind"],
        },
    },
    {
        "name": "browser_find",
        "description": (
            "Find elements by role/name/text with scoped grounding. "
            "Use scope=nav for Issues/PRs/Code tabs to avoid commit/PR body false matches."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "role": {"type": "string"},
                "name": {"type": "string"},
                "text": {"type": "string"},
                "exact": {"type": "boolean", "default": False},
                "scope": {
                    "type": "string",
                    "enum": ["any", "nav", "main", "form"],
                    "default": "any",
                },
            },
        },
    },
    {
        "name": "browser_network",
        "description": "List recent captured API/XHR requests (summaries).",
        "parameters": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "substring/glob/re: pattern"},
                "graphql_only": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "browser_resync",
        "description": "Full semantic resync when refs look stale. Expensive; use sparingly.",
        "parameters": {
            "type": "object",
            "properties": {
                "detail": {
                    "type": "string",
                    "enum": ["sparse", "normal", "full"],
                    "default": "normal",
                }
            },
        },
    },
    {
        "name": "browser_prepare",
        "description": (
            "Settle SPA (domcontentloaded/networkidle budget), dismiss cookie/consent "
            "overlays, optional scroll probe. Call after heavy navigations if observe looks empty."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
]


def tools_as_openai() -> list[dict[str, Any]]:
    """OpenAI Chat Completions / compatible tools format."""
    out = []
    for t in TOOL_DEFINITIONS:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
        )
    return out


def tools_as_anthropic() -> list[dict[str, Any]]:
    """Anthropic Messages API tools format."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        for t in TOOL_DEFINITIONS
    ]


def tool_names() -> list[str]:
    return [t["name"] for t in TOOL_DEFINITIONS]
