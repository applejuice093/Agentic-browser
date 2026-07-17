"""
Minimal custom agent using OpenAI-compatible tool schemas + agent-browser.

Requires: pip install openai
  set OPENAI_API_KEY=...

    python examples/openai_tool_agent.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_browser import Browser, tools_as_openai


async def run(goal: str = "Open example.com and tell me the page title and main heading.") -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("No OPENAI_API_KEY — running offline tool smoke instead.")
        async with Browser(headless=True) as browser:
            agent = await browser.open_agent("https://example.com", settle=True)
            obs = await agent.observe()
            print("title:", obs.title)
            print("summary:", obs.summary)
            print("tools available:", [t["function"]["name"] for t in tools_as_openai()])
        return

    from openai import OpenAI

    client = OpenAI()
    tools = tools_as_openai()

    async with Browser(headless=True) as browser:
        agent = await browser.open_agent("about:blank", settle=False)
        messages: list[dict] = [
            {
                "role": "system",
                "content": (
                    "You control a browser via tools. "
                    "Navigate, observe, check page_gate, then answer. "
                    "Never invent page content if blocked."
                ),
            },
            {"role": "user", "content": goal},
        ]
        for step in range(8):
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                tools=tools,
            )
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_unset=True))
            if not msg.tool_calls:
                print("ASSISTANT:", msg.content)
                return
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                print(f"[step {step}] tool {name} {args}")
                result = await agent.call_tool(name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str)[:12000],
                    }
                )
        print("Stopped after max steps.")


if __name__ == "__main__":
    asyncio.run(run())
