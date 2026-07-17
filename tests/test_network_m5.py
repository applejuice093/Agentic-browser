"""M5 network intelligence tests."""

from __future__ import annotations

import asyncio
import json

import pytest

from agent_browser import Browser, NetworkTimeoutError
from agent_browser.network.graphql import is_graphql_request, parse_graphql_payload

# about:blank cannot resolve relative fetch(); use an https origin + base href
BASE = "https://agent-browser.test"


def _page_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><base href="{BASE}/"></head>
<body>
{body}
</body>
</html>
"""


def test_graphql_detection_and_parse():
    body = json.dumps(
        {
            "operationName": "GetCart",
            "query": "query GetCart {{ cart {{ id }} }}".replace("{{", "{").replace("}}", "}"),
            "variables": {"id": 1},
        }
    )
    # fix query string properly
    body = json.dumps(
        {
            "operationName": "GetCart",
            "query": "query GetCart { cart { id } }",
            "variables": {"id": 1},
        }
    )
    assert is_graphql_request(
        url="https://shop.test/graphql",
        method="POST",
        headers={"content-type": "application/json"},
        post_data=body,
    )
    meta = parse_graphql_payload(body)
    assert meta["operation"] == "query"
    assert meta["query_name"] == "GetCart"
    assert meta["variables"] == {"id": 1}


def test_graphql_url_heuristic():
    assert is_graphql_request(
        url="https://api.test/gql",
        method="GET",
        headers={},
        post_data=None,
    )


@pytest.mark.asyncio
async def test_network_capture_and_filter():
    async with Browser(headless=True) as browser:
        page = await browser.new_page()
        await page.route(f"{BASE}/api/cart**", fulfill_json={"items": 2, "total": 9.99})
        # also match wildcard style
        await page.route("**/api/cart**", fulfill_json={"items": 2, "total": 9.99})
        await page.set_content(
            _page_html(
                """
              <button id="load">Load</button>
              <script>
                document.getElementById('load').onclick = () => {
                  fetch('api/cart', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json',
                              'Authorization': 'Bearer secret'},
                    body: JSON.stringify({op: 'get'})
                  }).then(r => r.json()).then(j => {
                    document.body.dataset.ok = String(j.items);
                  });
                };
              </script>
                """
            )
        )
        page.clear_network_log()
        await page.click("#load")
        req = await page.wait_for_api("/api/cart", timeout_ms=15_000)
        assert req.response_status == 200
        assert req.method == "POST"
        assert "items" in (req.response_body or "")
        auth = {k.lower(): v for k, v in req.headers.items()}.get("authorization")
        assert auth == "***"

        summaries = page.network_requests(filter="cart")
        assert len(summaries) >= 1
        assert summaries[0]["status"] == 200

        status = await page.evaluate("() => document.body.dataset.ok")
        assert status == "2"


@pytest.mark.asyncio
async def test_wait_for_api_timeout():
    async with Browser(headless=True) as browser:
        page = await browser.set_content(_page_html("hi"))
        with pytest.raises(NetworkTimeoutError):
            await page.wait_for_api("/never-called", timeout_ms=300)


@pytest.mark.asyncio
async def test_graphql_capture():
    async with Browser(headless=True) as browser:
        page = await browser.new_page()
        await page.route("**/graphql", fulfill_json={"data": {"cart": {"id": "c1"}}})
        await page.set_content(_page_html("gql"))
        page.clear_network_log()

        task = asyncio.create_task(
            page.evaluate(
                """async () => {
                  await fetch('graphql', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                      operationName: 'GetCart',
                      query: 'query GetCart { cart { id } }'
                    })
                  });
                }"""
            )
        )
        req = await page.wait_for_api("graphql", timeout_ms=15_000)
        await task
        assert req.is_graphql
        assert req.graphql_query_name == "GetCart"
        gql_list = page.network_requests(graphql_only=True)
        assert len(gql_list) >= 1


@pytest.mark.asyncio
async def test_api_call_event_emitted():
    async with Browser(headless=True) as browser:
        page = await browser.new_page()
        await page.route("**/api/ping", fulfill_json={"pong": True})
        await page.set_content(_page_html(""))
        seen: list = []
        page.on_event("api_call", lambda e: seen.append(e))
        page.clear_network_log()
        await page.evaluate("() => fetch('api/ping')")
        for _ in range(50):
            if seen:
                break
            await asyncio.sleep(0.05)
        assert seen, "expected api_call event"
        assert "ping" in seen[0].data.get("url", "")
