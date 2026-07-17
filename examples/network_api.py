"""
M5 example: mock API, capture traffic, wait_for_api, GraphQL flag.

    python examples/network_api.py
"""

from __future__ import annotations

import asyncio
import json

from agent_browser import Browser

BASE = "https://agent-browser.test"


async def main() -> None:
    async with Browser(headless=True) as browser:
        page = await browser.new_page()
        await page.route("**/api/cart**", fulfill_json={"items": [{"sku": "A"}], "total": 12})
        await page.route(
            "**/graphql",
            fulfill_json={"data": {"viewer": {"name": "Ada"}}},
        )
        await page.set_content(
            f"""
            <html>
            <head><base href="{BASE}/"></head>
            <body>
              <button id="cart">Load cart</button>
              <button id="gql">GraphQL</button>
              <pre id="out"></pre>
              <script>
                document.getElementById('cart').onclick = async () => {{
                  const r = await fetch('api/cart', {{ method: 'POST',
                    headers: {{'Content-Type':'application/json','Authorization':'Bearer x'}},
                    body: '{{}}' }});
                  document.getElementById('out').textContent = await r.text();
                }};
                document.getElementById('gql').onclick = async () => {{
                  const r = await fetch('graphql', {{
                    method: 'POST',
                    headers: {{'Content-Type':'application/json'}},
                    body: JSON.stringify({{
                      operationName: 'Viewer',
                      query: 'query Viewer {{ viewer {{ name }} }}'
                    }})
                  }});
                  document.getElementById('out').textContent = await r.text();
                }};
              </script>
            </body></html>
            """
        )

        page.on_event(
            "api_call",
            lambda e: print(" event api_call", e.data.get("url"), e.data.get("status")),
        )

        page.clear_network_log()
        await page.click("#cart")
        cart = await page.wait_for_api("/api/cart", timeout_ms=15_000)
        print("cart status", cart.response_status, "body", cart.response_body)
        print(
            "auth header masked?",
            cart.headers.get("authorization") or cart.headers.get("Authorization"),
        )

        await page.click("#gql")
        gql = await page.wait_for_api("graphql", timeout_ms=15_000)
        print("graphql?", gql.is_graphql, gql.graphql_query_name, gql.response_body)

        print("all summaries:", json.dumps(page.network_requests(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
