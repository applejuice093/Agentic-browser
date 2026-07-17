"""
Complex-site comparison: traditional HTTP scrape vs agent-browser.

Target: https://www.rockstargames.com/VI

Produces two "landing page" style JSON payloads an LLM might receive,
plus percentage metrics.

    python examples/compare_rockstar_vi.py
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from agent_browser import Browser

URL = "https://www.rockstargames.com/VI"
OUT_DIR = Path("data/rockstar_vi_compare")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def approx_tokens(text: str) -> int:
    return max(0, (len(text) + 3) // 4)


def pct(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 1)


def reduction(new: float, old: float) -> float:
    if old <= 0:
        return 0.0
    return round(100.0 * (1.0 - new / old), 1)


# ---------------------------------------------------------------------------
# Traditional: httpx + BeautifulSoup (no JS execution)
# ---------------------------------------------------------------------------


async def traditional_landing() -> dict[str, Any]:
    t0 = time.perf_counter()
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    error = None
    status = None
    html = ""
    try:
        async with httpx.AsyncClient(
            timeout=45.0,
            follow_redirects=True,
            headers=headers,
        ) as client:
            r = await client.get(URL)
            status = r.status_code
            html = r.text
            final_url = str(r.url)
    except Exception as exc:
        error = str(exc)
        final_url = URL
        status = None

    elapsed = (time.perf_counter() - t0) * 1000
    soup = BeautifulSoup(html, "lxml") if html else BeautifulSoup("", "lxml")

    # Remove script/style for "visible" text path
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = (soup.title.string or "").strip() if soup.title else ""
    meta_desc = ""
    md = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if md and md.get("content"):
        meta_desc = md["content"].strip()

    headings = []
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        t = h.get_text(" ", strip=True)
        if t:
            headings.append({"tag": h.name, "text": t[:200]})

    links = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)[:120]
        href = a["href"]
        if text or href:
            links.append({"text": text or None, "href": href[:300]})

    buttons = []
    for b in soup.find_all(["button", "input"]):
        if b.name == "input" and (b.get("type") or "").lower() not in (
            "button",
            "submit",
            "reset",
        ):
            continue
        label = (
            b.get_text(" ", strip=True)
            or b.get("value")
            or b.get("aria-label")
            or b.get("name")
            or ""
        )
        if label:
            buttons.append({"text": label[:120], "type": b.name})

    visible_text = soup.get_text("\n", strip=True)
    visible_text = re.sub(r"\n{3,}", "\n\n", visible_text)

    # What we'd typically feed an LLM in "traditional" mode
    llm_payload = {
        "source": "traditional_http_bs4",
        "url": final_url,
        "http_status": status,
        "title": title,
        "meta_description": meta_desc,
        "headings": headings[:40],
        "links": links[:80],
        "buttons": buttons[:40],
        "visible_text_sample": visible_text[:4000],
        "raw_html_chars": len(html),
        "error": error,
        "note": "No JavaScript execution — SPA shells often look empty.",
    }

    # Also measure pure raw HTML feed size
    raw_feed_tokens = approx_tokens(html)
    structured_json = json.dumps(llm_payload, ensure_ascii=False)
    text_feed_tokens = approx_tokens(visible_text)

    return {
        "method": "traditional",
        "latency_ms": round(elapsed, 1),
        "landing_page": llm_payload,
        "metrics": {
            "http_status": status,
            "raw_html_chars": len(html),
            "raw_html_tokens_approx": raw_feed_tokens,
            "visible_text_chars": len(visible_text),
            "visible_text_tokens_approx": text_feed_tokens,
            "structured_json_chars": len(structured_json),
            "structured_json_tokens_approx": approx_tokens(structured_json),
            "heading_count": len(headings),
            "link_count": len(links),
            "button_count": len(buttons),
            "actionable_refs": 0,
            "js_rendered": False,
            "error": error,
        },
        "llm_feed_recommendation": {
            "if_raw_html_tokens": raw_feed_tokens,
            "if_visible_text_tokens": text_feed_tokens,
            "if_structured_tokens": approx_tokens(structured_json),
        },
    }


# ---------------------------------------------------------------------------
# Agent browser: full JS, compact observation, semantic scrape
# ---------------------------------------------------------------------------


async def agent_landing() -> dict[str, Any]:
    t0 = time.perf_counter()
    error = None
    async with Browser(headless=True) as browser:
        try:
            page = await browser.open(URL)
            # Complex SPA — give it time to hydrate
            try:
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            await asyncio.sleep(3.0)
            try:
                await page.wait_for_load_state("networkidle")
            except Exception:
                pass
            await asyncio.sleep(1.5)

            agent = page.as_agent(detail="normal", max_tokens=2500)
            obs = await agent.observe(detail="normal", max_tokens=2500, include_diff=False)

            # Full semantic counts (debug)
            snap = page.last_snapshot
            raw_html = await page.content()
            title = await page.title()

            # Try to find primary CTAs via agent finders
            cta_candidates = []
            for role, name in (
                ("link", "Watch"),
                ("button", "Watch"),
                ("link", "Trailer"),
                ("button", "Trailer"),
                ("link", "Buy"),
                ("link", "Play"),
                ("link", "Order"),
            ):
                try:
                    hits = await agent.find(role=role, text=name)
                    for h in hits[:3]:
                        cta_candidates.append(h)
                except Exception:
                    pass

            network = page.network_requests()
            api_like = [
                n
                for n in network
                if any(
                    x in (n.get("url") or "").lower()
                    for x in ("api", "graphql", "json", "trailer", "video")
                )
            ][:25]

            # Visible text via browser (post-JS)
            body_text = await page.evaluate(
                """() => {
                  const t = (document.body && document.body.innerText) || '';
                  return t.replace(/\\s+/g, ' ').trim().slice(0, 5000);
                }"""
            )
            heading_texts = await page.evaluate(
                """() => Array.from(document.querySelectorAll('h1,h2,h3'))
                    .map(h => ({tag: h.tagName.toLowerCase(), text: (h.innerText||'').trim().slice(0,200)}))
                    .filter(x => x.text).slice(0, 40)"""
            )

            elapsed = (time.perf_counter() - t0) * 1000
            landing = {
                "source": "agent_browser",
                "url": page.url,
                "title": title,
                "observation": obs.to_llm_dict(),
                "headings_from_dom": heading_texts,
                "cta_candidates": cta_candidates,
                "interactive_sample": [
                    r.model_dump(exclude_none=True) for r in obs.interactive[:25]
                ],
                "body_text_sample": body_text[:4000],
                "network_api_sample": api_like,
                "semantic_element_total": len(snap.elements) if snap else 0,
                "note": "JS executed; compact observation for LLM + actionable refs.",
            }

            obs_json = json.dumps(obs.to_llm_dict(), ensure_ascii=False)
            return {
                "method": "agent_browser",
                "latency_ms": round(elapsed, 1),
                "landing_page": landing,
                "metrics": {
                    "http_status": None,
                    "final_url": page.url,
                    "raw_html_chars": len(raw_html),
                    "raw_html_tokens_approx": approx_tokens(raw_html),
                    "body_text_chars": len(body_text or ""),
                    "body_text_tokens_approx": approx_tokens(body_text or ""),
                    "observation_chars": len(obs_json),
                    "observation_tokens_approx": obs.approx_tokens,
                    "heading_count": len(heading_texts or []),
                    "interactive_count": len(obs.interactive),
                    "actionable_refs": len(obs.interactive),
                    "network_requests_captured": len(network),
                    "api_like_requests": len(api_like),
                    "js_rendered": True,
                    "truncated": obs.truncated,
                    "error": None,
                },
                "llm_feed_recommendation": {
                    "if_raw_html_tokens": approx_tokens(raw_html),
                    "if_body_text_tokens": approx_tokens(body_text or ""),
                    "if_observation_tokens": obs.approx_tokens,
                },
            }
        except Exception as exc:
            error = str(exc)
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "method": "agent_browser",
                "latency_ms": round(elapsed, 1),
                "landing_page": {"error": error, "url": URL},
                "metrics": {
                    "error": error,
                    "js_rendered": True,
                    "actionable_refs": 0,
                    "observation_tokens_approx": 0,
                    "raw_html_tokens_approx": 0,
                    "body_text_tokens_approx": 0,
                    "heading_count": 0,
                    "interactive_count": 0,
                    "network_requests_captured": 0,
                },
                "llm_feed_recommendation": {},
            }


def build_comparison(trad: dict, agent: dict) -> dict[str, Any]:
    tm, am = trad["metrics"], agent["metrics"]

    raw_t = tm.get("raw_html_tokens_approx") or 0
    raw_a = am.get("raw_html_tokens_approx") or 0
    # Baseline for "what LLM would get fed" traditionally = raw HTML if non-empty else text
    trad_feed = tm.get("structured_json_tokens_approx") or tm.get("visible_text_tokens_approx") or 0
    trad_raw = raw_t
    agent_obs = am.get("observation_tokens_approx") or 0
    agent_text = am.get("body_text_tokens_approx") or 0

    content_signals = {
        "traditional_headings": tm.get("heading_count") or 0,
        "agent_headings": am.get("heading_count") or 0,
        "traditional_links": tm.get("link_count") or 0,
        "agent_interactive_refs": am.get("interactive_count") or 0,
        "traditional_buttons": tm.get("button_count") or 0,
        "traditional_visible_text_chars": tm.get("visible_text_chars") or 0,
        "agent_body_text_chars": am.get("body_text_chars") or 0,
    }

    # "Usable content" heuristic: headings + substantial text
    trad_usable = (content_signals["traditional_headings"] > 0) or (
        content_signals["traditional_visible_text_chars"] > 200
    )
    agent_usable = (content_signals["agent_headings"] > 0) or (
        content_signals["agent_body_text_chars"] > 200
    ) or (content_signals["agent_interactive_refs"] > 0)

    return {
        "url": URL,
        "latency": {
            "traditional_ms": trad.get("latency_ms"),
            "agent_ms": agent.get("latency_ms"),
            "agent_slower_by_pct": (
                pct(agent["latency_ms"] - trad["latency_ms"], trad["latency_ms"])
                if trad.get("latency_ms")
                else None
            ),
        },
        "llm_input_tokens": {
            "traditional_raw_html": trad_raw,
            "traditional_visible_text": tm.get("visible_text_tokens_approx"),
            "traditional_structured_json": tm.get("structured_json_tokens_approx"),
            "agent_raw_html_after_js": raw_a,
            "agent_body_text": agent_text,
            "agent_compact_observation": agent_obs,
        },
        "percentages": {
            "agent_observation_vs_traditional_raw_html_reduction_pct": reduction(
                agent_obs, trad_raw
            )
            if trad_raw
            else None,
            "agent_observation_as_pct_of_traditional_raw_html": pct(agent_obs, trad_raw)
            if trad_raw
            else None,
            "agent_observation_vs_agent_raw_html_reduction_pct": reduction(agent_obs, raw_a)
            if raw_a
            else None,
            "agent_observation_as_pct_of_agent_raw_html": pct(agent_obs, raw_a)
            if raw_a
            else None,
            "agent_text_vs_traditional_text_size_pct": pct(
                agent_text, tm.get("visible_text_tokens_approx") or 1
            ),
            "traditional_usable_content_detected": trad_usable,
            "agent_usable_content_detected": agent_usable,
            "actionable_refs_traditional": 0,
            "actionable_refs_agent": am.get("actionable_refs") or 0,
            "js_execution_traditional": False,
            "js_execution_agent": True,
        },
        "content_signals": content_signals,
        "winner_by_dimension": {
            "js_spa_content": "agent" if agent_usable and not trad_usable else (
                "tie" if agent_usable and trad_usable else (
                    "traditional" if trad_usable else "neither_clear"
                )
            ),
            "llm_token_efficiency": (
                "agent_observation"
                if agent_obs and trad_raw and agent_obs < trad_raw
                else "depends"
            ),
            "actionability": "agent",
            "speed": "traditional"
            if (trad.get("latency_ms") or 0) < (agent.get("latency_ms") or 1e9)
            else "agent",
            "network_introspection": "agent"
            if (am.get("network_requests_captured") or 0) > 0
            else "n/a",
        },
    }


def print_report(comp: dict, trad: dict, agent: dict) -> None:
    print("\n" + "=" * 72)
    print("COMPLEX SITE: Rockstar GTA VI landing")
    print(URL)
    print("=" * 72)
    tm, am = trad["metrics"], agent["metrics"]
    print("\n--- Traditional (httpx + BeautifulSoup, no JS) ---")
    print(f"  status:     {tm.get('http_status')}  error: {tm.get('error')}")
    print(f"  latency:    {trad.get('latency_ms')} ms")
    print(f"  raw HTML:   {tm.get('raw_html_tokens_approx')} tokens ({tm.get('raw_html_chars')} chars)")
    print(f"  vis text:   {tm.get('visible_text_tokens_approx')} tokens")
    print(f"  structured: {tm.get('structured_json_tokens_approx')} tokens")
    print(f"  headings:   {tm.get('heading_count')}  links: {tm.get('link_count')}  buttons: {tm.get('button_count')}")
    print(f"  actionable: 0 refs")

    print("\n--- Agent browser (Playwright + compact observation) ---")
    print(f"  error:      {am.get('error')}")
    print(f"  latency:    {agent.get('latency_ms')} ms")
    print(f"  final url:  {am.get('final_url')}")
    print(f"  raw HTML:   {am.get('raw_html_tokens_approx')} tokens (after JS)")
    print(f"  body text:  {am.get('body_text_tokens_approx')} tokens")
    print(f"  observation:{am.get('observation_tokens_approx')} tokens (LLM feed)")
    print(f"  headings:   {am.get('heading_count')}  interactive: {am.get('interactive_count')}")
    print(f"  actionable: {am.get('actionable_refs')} refs")
    print(f"  network:    {am.get('network_requests_captured')} requests")

    p = comp["percentages"]
    print("\n--- Percentage comparison ---")
    if p.get("agent_observation_vs_traditional_raw_html_reduction_pct") is not None:
        print(
            f"  Agent observation vs traditional raw HTML: "
            f"{p['agent_observation_as_pct_of_traditional_raw_html']}% of size "
            f"({p['agent_observation_vs_traditional_raw_html_reduction_pct']}% reduction)"
        )
    if p.get("agent_observation_vs_agent_raw_html_reduction_pct") is not None:
        print(
            f"  Agent observation vs post-JS raw HTML: "
            f"{p['agent_observation_as_pct_of_agent_raw_html']}% of size "
            f"({p['agent_observation_vs_agent_raw_html_reduction_pct']}% reduction)"
        )
    print(f"  Traditional usable content: {p['traditional_usable_content_detected']}")
    print(f"  Agent usable content:       {p['agent_usable_content_detected']}")
    print(f"  Actionable refs:            trad=0  agent={p['actionable_refs_agent']}")
    if comp["latency"].get("agent_slower_by_pct") is not None:
        print(f"  Agent latency vs trad:      +{comp['latency']['agent_slower_by_pct']}%")
    print("\n--- Winners ---")
    for k, v in comp["winner_by_dimension"].items():
        print(f"  {k}: {v}")
    print("=" * 72)


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching traditional…")
    trad = await traditional_landing()
    print("Fetching agent browser (may take ~30–90s for SPA)…")
    agent = await agent_landing()
    comp = build_comparison(trad, agent)

    (OUT_DIR / "landing_traditional.json").write_text(
        json.dumps(trad, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    (OUT_DIR / "landing_agent.json").write_text(
        json.dumps(agent, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    (OUT_DIR / "comparison.json").write_text(
        json.dumps(comp, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    print_report(comp, trad, agent)
    print(f"\nWrote: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
