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
        "description": "Click an element by ref (integer from observation.interactive[].ref).",
        "parameters": {
            "type": "object",
            "properties": {
                "ref": {"type": "integer", "description": "Stable element ref"},
                "observe": {
                    "type": "boolean",
                    "default": True,
                    "description": "Return post-action observation",
                },
            },
            "required": ["ref"],
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
        "description": "Find elements by role/name/text without CSS. Returns matching refs.",
        "parameters": {
            "type": "object",
            "properties": {
                "role": {"type": "string"},
                "name": {"type": "string"},
                "text": {"type": "string"},
                "exact": {"type": "boolean", "default": False},
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
]


def tools_as_openai() -> list[dict[str, Any]]:
    """OpenAI Chat Completions tools format."""
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


def tool_names() -> list[str]:
    return [t["name"] for t in TOOL_DEFINITIONS]
