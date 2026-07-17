"""
Agent-native loop demo (compact observe → click by ref).

    python examples/agent_loop_demo.py
"""

from __future__ import annotations

import asyncio
import json

from agent_browser import Browser, tools_as_openai


async def main() -> None:
    print("Tools available:", [t["function"]["name"] for t in tools_as_openai()])

    async with Browser(headless=True) as browser:
        agent = await browser.open_agent("https://quotes.toscrape.com", detail="normal")

        obs = await agent.observe(max_tokens=1200)
        print("\n=== Observation (LLM payload) ===")
        print(json.dumps(obs.to_llm_dict(), indent=2)[:1200], "…")
        print(f"\napprox_tokens={obs.approx_tokens} interactive={len(obs.interactive)}")

        # Prefer semantic Next via tool API
        matches = await agent.find(role="link", text="Next")
        print("find Next:", matches[:3])
        if matches:
            result = await agent.click(matches[0]["ref"])
            print("\n=== ActionResult ===")
            print(
                json.dumps(
                    {
                        "ok": result.ok,
                        "action": result.action,
                        "error_code": result.error_code,
                        "navigated": result.navigated,
                        "url_after": result.url_after,
                        "obs_tokens": (
                            result.observation.approx_tokens if result.observation else None
                        ),
                        "obs_url": result.observation.url if result.observation else None,
                    },
                    indent=2,
                )
            )

        # Tool dispatch style (as an LLM would)
        net = await agent.call_tool("browser_network", {"filter": "quotes"})
        print("network tool:", net.get("requests", [])[:2])


if __name__ == "__main__":
    asyncio.run(main())
