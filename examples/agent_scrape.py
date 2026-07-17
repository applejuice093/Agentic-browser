"""
Agent-first scrape demo.

Uses semantic snapshots (not raw HTML soup) to extract structured data
from a public practice site: https://quotes.toscrape.com

Usage:
    python examples/agent_scrape.py
    python examples/agent_scrape.py --url https://books.toscrape.com
    python examples/agent_scrape.py --out data/scrape.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

# Allow running without install when cwd is repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_browser import Browser
from agent_browser.scrape import scrape_page


async def scrape_quotes_site(url: str, *, headless: bool = True) -> dict:
    """
    Domain-aware scrape for quotes.toscrape.com using agent finders + JS assist.

    Strategy:
      1. Navigate with agent Browser
      2. Semantic snapshot for roles/links
      3. Evaluate a small in-page extractor for quote cards (stable site markup)
      4. Merge network log + LLM-oriented context
    """
    async with Browser(headless=headless) as browser:
        page = await browser.open(url)
        await page.wait_for_load_state("domcontentloaded")

        # Agent world model
        base = await scrape_page(
            page,
            include_network=True,
            goal="extract all quotes, authors, and tags from this page",
        )

        # Site-specific structured extract (agent would learn/call this as a tool)
        quotes = await page.evaluate(
            """() => {
              const cards = Array.from(document.querySelectorAll('.quote'));
              return cards.map(q => ({
                text: (q.querySelector('.text') || {}).innerText || '',
                author: (q.querySelector('.author') || {}).innerText || '',
                tags: Array.from(q.querySelectorAll('.tag')).map(t => t.innerText),
              }));
            }"""
        )

        # Prefer semantic links for pagination / tags
        next_link = await page.find(role="link", text_contains="Next")
        tag_links = [
            e
            for e in (await page.find_all(role="link", refresh=False))
            if e.attributes.get("href") and "/tag/" in (e.attributes.get("href") or "")
        ][:20]

        plan = await page.plan(
            "collect all quotes on this page then go to next page if available",
            refresh=False,
        )

        return {
            "source": url,
            "title": base.get("title"),
            "page_url": base.get("url"),
            "quotes": quotes,
            "quote_count": len(quotes),
            "next_page": {
                "available": next_link is not None,
                "element_id": next_link.id if next_link else None,
                "text": next_link.text if next_link else None,
                "href": (next_link.attributes.get("href") if next_link else None),
            },
            "tag_links": [
                {"text": t.text, "href": t.attributes.get("href"), "id": t.id}
                for t in tag_links
            ],
            "semantic_summary": base.get("counts"),
            "headings": base.get("headings"),
            "agent_context": base.get("context"),
            "agent_plan": plan,
            "network_calls": base.get("network"),
            "session_id": browser.session_id,
        }


async def scrape_generic(url: str, *, headless: bool = True) -> dict:
    """Generic agent scrape for any public URL (headings, links, buttons, fields)."""
    async with Browser(headless=headless) as browser:
        page = await browser.open(url)
        data = await scrape_page(
            page,
            include_network=True,
            goal="extract main content, headings, and important links",
        )
        data["source"] = url
        data["session_id"] = browser.session_id
        # Extra: visible text sample via evaluate
        data["text_sample"] = await page.evaluate(
            """() => {
              const t = (document.body && document.body.innerText) || '';
              return t.replace(/\\s+/g, ' ').trim().slice(0, 2000);
            }"""
        )
        return data


async def scrape_quotes_multi_page(
    start_url: str,
    *,
    max_pages: int = 2,
    headless: bool = True,
) -> dict:
    """Follow 'Next' via agent click and accumulate quotes."""
    all_quotes: list[dict] = []
    pages_meta: list[dict] = []

    async with Browser(headless=headless) as browser:
        page = await browser.open(start_url)
        for i in range(max_pages):
            await page.wait_for_load_state("domcontentloaded")
            quotes = await page.evaluate(
                """() => Array.from(document.querySelectorAll('.quote')).map(q => ({
                  text: (q.querySelector('.text')||{}).innerText || '',
                  author: (q.querySelector('.author')||{}).innerText || '',
                  tags: Array.from(q.querySelectorAll('.tag')).map(t => t.innerText),
                  page: null
                }))"""
            )
            for q in quotes:
                q["page"] = i + 1
                q["page_url"] = page.url
            all_quotes.extend(quotes)
            pages_meta.append({"index": i + 1, "url": page.url, "count": len(quotes)})

            next_el = await page.find(role="link", text_contains="Next", refresh=True)
            if not next_el:
                break
            await page.click(next_el.id)
            await page.wait_for_load_state("domcontentloaded")

        return {
            "source": start_url,
            "pages_scraped": len(pages_meta),
            "quote_count": len(all_quotes),
            "pages": pages_meta,
            "quotes": all_quotes,
            "session_id": browser.session_id,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Browser scrape demo")
    parser.add_argument(
        "--url",
        default="https://quotes.toscrape.com",
        help="URL to scrape (default: quotes.toscrape.com)",
    )
    parser.add_argument(
        "--out",
        default="data/scrape_result.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="For quotes site: number of pages to follow (default 1)",
    )
    parser.add_argument("--headed", action="store_true", help="Show browser UI")
    args = parser.parse_args()

    headless = not args.headed
    url = args.url

    async def run() -> dict:
        if "quotes.toscrape.com" in url and args.pages > 1:
            return await scrape_quotes_multi_page(
                url, max_pages=args.pages, headless=headless
            )
        if "quotes.toscrape.com" in url:
            return await scrape_quotes_site(url, headless=headless)
        return await scrape_generic(url, headless=headless)

    result = asyncio.run(run())

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Console summary
    print("=== Agent scrape complete ===")
    print("url:", result.get("page_url") or result.get("source"))
    print("title:", result.get("title"))
    if "quotes" in result:
        print("quotes:", result.get("quote_count"))
        for q in result["quotes"][:5]:
            text = re.sub(r"\s+", " ", q.get("text") or "")[:80]
            print(f"  - {q.get('author')}: {text}…")
        if result.get("next_page"):
            print("next page:", result["next_page"])
    else:
        counts = result.get("counts") or result.get("semantic_summary")
        print("counts:", counts)
        for h in (result.get("headings") or [])[:5]:
            print("  heading:", (h.get("text") or "")[:80])
    print("saved:", out_path.resolve())


if __name__ == "__main__":
    main()
