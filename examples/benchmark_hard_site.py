"""
No-sugarcoating benchmark: traditional HTTP vs agent-browser on a hard site.

Default target: GitHub (agents hit this constantly — SPA, lazy UI, auth chrome).

    python examples/benchmark_hard_site.py
    python examples/benchmark_hard_site.py --url https://www.reddit.com/r/MachineLearning/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from agent_browser import Browser

# Coding agents' daily bread — complex React SPA, lots of chrome, partial SSR
DEFAULT_URL = "https://github.com/vercel/next.js"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def tok(s: str) -> int:
    return max(0, (len(s) + 3) // 4)


def pct(a: float, b: float) -> float:
    return round(100.0 * a / b, 1) if b else 0.0


def red(new: float, old: float) -> float:
    return round(100.0 * (1.0 - new / old), 1) if old else 0.0


def score_content(text: str, signals: list[str]) -> dict[str, Any]:
    low = (text or "").lower()
    hits = [s for s in signals if s.lower() in low]
    return {
        "signals_checked": signals,
        "signals_found": hits,
        "signal_hit_rate_pct": pct(len(hits), len(signals)) if signals else 0.0,
        "text_chars": len(text or ""),
        "text_tokens": tok(text or ""),
    }


async def traditional(url: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    err = None
    status = None
    html = ""
    final = url
    try:
        async with httpx.AsyncClient(
            timeout=40.0,
            follow_redirects=True,
            headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
        ) as client:
            r = await client.get(url)
            status = r.status_code
            html = r.text
            final = str(r.url)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    ms = (time.perf_counter() - t0) * 1000
    soup = BeautifulSoup(html, "lxml") if html else BeautifulSoup("", "lxml")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    headings = [
        {"tag": h.name, "text": h.get_text(" ", strip=True)[:160]}
        for h in soup.find_all(re.compile(r"^h[1-6]$"))
        if h.get_text(strip=True)
    ][:30]
    links = []
    for a in soup.find_all("a", href=True)[:100]:
        links.append(
            {
                "text": (a.get_text(" ", strip=True) or "")[:100] or None,
                "href": a["href"][:250],
            }
        )
    structured = {
        "source": "traditional_http",
        "url": final,
        "status": status,
        "title": title,
        "headings": headings,
        "link_count": len(links),
        "links_sample": links[:25],
        "text_sample": text[:3500],
        "error": err,
    }
    return {
        "method": "traditional",
        "latency_ms": round(ms, 1),
        "error": err,
        "status": status,
        "final_url": final,
        "raw_html_chars": len(html),
        "raw_html_tokens": tok(html),
        "text_chars": len(text),
        "text_tokens": tok(text),
        "structured_tokens": tok(json.dumps(structured, ensure_ascii=False)),
        "heading_count": len(headings),
        "link_count": len(links),
        "actionable_refs": 0,
        "js_executed": False,
        "payload": structured,
    }


async def agent_run(url: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    err = None
    try:
        async with Browser(headless=True) as browser:
            agent = await browser.open_agent(
                url,
                detail="normal",
                max_tokens=2200,
                settle=True,
                settle_budget_ms=12_000,
            )
            obs = await agent.observe(prepare=False, max_tokens=2200, include_diff=False)
            raw = await agent.page.content()
            body = await agent.page.evaluate(
                """() => ((document.body && document.body.innerText) || '')
                    .replace(/\\s+/g,' ').trim().slice(0, 5000)"""
            )
            # Try agent finds for common GitHub actions
            finds = {}
            for role, text in (
                ("link", "Code"),
                ("link", "Issues"),
                ("link", "Pull requests"),
                ("button", "Code"),
                ("link", "README"),
                ("textbox", "Search"),
            ):
                try:
                    finds[f"{role}:{text}"] = await agent.find(role=role, text=text)
                except Exception as e:
                    finds[f"{role}:{text}"] = [{"error": str(e)}]

            # Attempt one real agent action: open Issues if present
            action = None
            issue_hits = finds.get("link:Issues") or []
            if issue_hits and "ref" in issue_hits[0]:
                action = (
                    await agent.click(issue_hits[0]["ref"], text_hint="Issues")
                ).to_llm_dict()

            net = await agent.network()
            ms = (time.perf_counter() - t0) * 1000
            obs_d = obs.to_llm_dict()
            return {
                "method": "agent_browser",
                "latency_ms": round(ms, 1),
                "error": None,
                "status": None,
                "final_url": agent.page.url,
                "raw_html_chars": len(raw),
                "raw_html_tokens": tok(raw),
                "text_chars": len(body or ""),
                "text_tokens": tok(body or ""),
                "observation_tokens": obs.approx_tokens,
                "observation_chars": len(json.dumps(obs_d, ensure_ascii=False)),
                "heading_count": len(obs.headings),
                "interactive_count": len(obs.interactive),
                "actionable_refs": len(obs.interactive),
                "network_requests": len(net),
                "js_executed": True,
                "summary": obs.summary,
                "finds": {k: (v[:3] if isinstance(v, list) else v) for k, v in finds.items()},
                "action_result": action,
                "payload": {
                    "source": "agent_browser",
                    "url": agent.page.url,
                    "title": obs.title,
                    "summary": obs.summary,
                    "observation": obs_d,
                    "body_sample": (body or "")[:3500],
                    "network_sample": net[:8],
                },
            }
    except Exception as e:
        return {
            "method": "agent_browser",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "error": f"{type(e).__name__}: {e}",
            "js_executed": True,
            "actionable_refs": 0,
            "observation_tokens": 0,
            "raw_html_tokens": 0,
            "text_tokens": 0,
            "heading_count": 0,
            "interactive_count": 0,
            "network_requests": 0,
            "payload": {"error": str(e)},
        }


def compare(url: str, trad: dict, agent: dict, signals: list[str]) -> dict[str, Any]:
    trad_text = (trad.get("payload") or {}).get("text_sample") or ""
    agent_text = (agent.get("payload") or {}).get("body_sample") or ""
    agent_blob = " ".join(
        [
            agent.get("summary") or "",
            agent_text,
            json.dumps((agent.get("payload") or {}).get("observation") or {}, ensure_ascii=False),
        ]
    )
    trad_score = score_content(trad_text + " " + (trad.get("payload") or {}).get("title", ""), signals)
    agent_score = score_content(agent_blob, signals)

    t_raw = trad.get("raw_html_tokens") or 0
    a_obs = agent.get("observation_tokens") or 0
    a_raw = agent.get("raw_html_tokens") or 0

    failures = []
    if trad.get("error"):
        failures.append(f"traditional_error: {trad['error']}")
    if agent.get("error"):
        failures.append(f"agent_error: {agent['error']}")
    if (trad.get("status") or 0) >= 400:
        failures.append(f"traditional_http_{trad.get('status')}")
    if trad_score["signal_hit_rate_pct"] < 40:
        failures.append("traditional_weak_content_signals")
    if agent_score["signal_hit_rate_pct"] < 40:
        failures.append("agent_weak_content_signals")
    if (agent.get("latency_ms") or 0) > 15_000:
        failures.append("agent_slow_>15s")
    if (agent.get("actionable_refs") or 0) < 5:
        failures.append("agent_few_actionable_refs")
    action = agent.get("action_result")
    if action is not None and not action.get("ok"):
        failures.append(f"agent_action_failed: {action.get('error_code')}")

    return {
        "url": url,
        "why_this_site": (
            "GitHub is among the most common destinations for coding agents/LLMs "
            "(repos, issues, PRs, search). Heavy React SPA, auth chrome, lazy tabs."
        ),
        "latency_ms": {
            "traditional": trad.get("latency_ms"),
            "agent": agent.get("latency_ms"),
            "agent_vs_trad_multiplier": round(
                (agent.get("latency_ms") or 0) / max(trad.get("latency_ms") or 1, 1), 1
            ),
        },
        "tokens": {
            "traditional_raw_html": t_raw,
            "traditional_visible_text": trad.get("text_tokens"),
            "traditional_structured": trad.get("structured_tokens"),
            "agent_raw_html_after_js": a_raw,
            "agent_body_text": agent.get("text_tokens"),
            "agent_observation_llm_feed": a_obs,
            "observation_as_pct_of_trad_raw_html": pct(a_obs, t_raw) if t_raw else None,
            "observation_reduction_vs_trad_raw_pct": red(a_obs, t_raw) if t_raw else None,
            "observation_as_pct_of_agent_raw_html": pct(a_obs, a_raw) if a_raw else None,
            "observation_reduction_vs_agent_raw_pct": red(a_obs, a_raw) if a_raw else None,
        },
        "content_signal_hit_rate_pct": {
            "traditional": trad_score["signal_hit_rate_pct"],
            "agent": agent_score["signal_hit_rate_pct"],
            "traditional_found": trad_score["signals_found"],
            "agent_found": agent_score["signals_found"],
            "signals": signals,
        },
        "structure": {
            "traditional_headings": trad.get("heading_count"),
            "traditional_links": trad.get("link_count"),
            "agent_headings": agent.get("heading_count"),
            "agent_interactive_refs": agent.get("interactive_count"),
            "agent_network_requests": agent.get("network_requests"),
        },
        "actionability": {
            "traditional_refs": 0,
            "agent_refs": agent.get("actionable_refs") or 0,
            "agent_click_issues_attempt": agent.get("action_result"),
        },
        "failures_and_weaknesses": failures,
        "blunt_verdict": None,  # filled below
    }


def blunt_verdict(c: dict, trad: dict, agent: dict) -> str:
    lines = []
    sig_t = c["content_signal_hit_rate_pct"]["traditional"]
    sig_a = c["content_signal_hit_rate_pct"]["agent"]
    mult = c["latency_ms"]["agent_vs_trad_multiplier"]
    obs_red = c["tokens"].get("observation_reduction_vs_trad_raw_pct")
    action_ok = (agent.get("action_result") or {}).get("ok")

    if trad.get("error") and agent.get("error"):
        return "BOTH FAILED. Product is not demo-ready on this URL."
    if agent.get("error") and not trad.get("error"):
        return (
            f"AGENT FAILED ({agent.get('error')}); traditional still returned data. "
            "Not good enough as a default browser for this site class."
        )
    if not agent.get("error") and trad.get("error"):
        lines.append("Traditional failed; agent is the only working path here.")

    # content
    if sig_a < 50 and sig_t < 50:
        lines.append(
            f"CONTENT: BOTH WEAK (agent {sig_a}% vs trad {sig_t}% signal hit). "
            "Neither is a reliable page reader here without site-specific work."
        )
    elif sig_a < sig_t - 15:
        lines.append(
            f"CONTENT: TRADITIONAL WINS hard (agent {sig_a}% vs trad {sig_t}% signals). "
            "SSR/HTML dump beats our observe for pure reading on this page."
        )
    elif sig_a > sig_t + 15:
        lines.append(
            f"CONTENT: AGENT WINS (agent {sig_a}% vs trad {sig_t}% signals). "
            "JS rendering mattered."
        )
    else:
        lines.append(
            f"CONTENT: roughly TIE (agent {sig_a}% vs trad {sig_t}% signals)."
        )

    # tokens
    if obs_red is not None and obs_red > 90:
        lines.append(
            f"TOKENS: Agent observation is a large win vs raw HTML (~{obs_red}% smaller). "
            "Do not feed HTML to an LLM."
        )
    elif obs_red is not None and obs_red < 50:
        lines.append(
            f"TOKENS: Observation only {obs_red}% smaller than raw HTML — compression is mediocre here."
        )

    # speed
    if mult >= 10:
        lines.append(
            f"SPEED: Agent is ~{mult}x slower. Unacceptable for high-QPS scraping; "
            "acceptable only if you need actions."
        )
    elif mult >= 3:
        lines.append(f"SPEED: Agent ~{mult}x slower — expected for real browser, still a cost.")

    # action
    if (agent.get("actionable_refs") or 0) > 0:
        if action_ok is True:
            lines.append("ACTION: Agent clicked a real control successfully — traditional cannot.")
        elif action_ok is False:
            lines.append(
                "ACTION: Had refs but click FAILED. Action loop is not trustworthy yet on this UI."
            )
        else:
            lines.append(
                "ACTION: Has refs but no successful navigation click in this run "
                "(finders may have missed primary tabs)."
            )
    else:
        lines.append("ACTION: Almost no refs — agent loop is crippled on this page.")

    # overall
    if agent.get("error"):
        overall = "NOT GOOD ENOUGH for this site today."
    elif sig_a >= 60 and (agent.get("actionable_refs") or 0) >= 10 and mult < 20:
        overall = (
            "USABLE for agent tasks (read+act) with eyes open on latency; "
            "not a free lunch vs HTTP for pure text extraction."
        )
    elif sig_a >= 40 and (agent.get("actionable_refs") or 0) >= 5:
        overall = (
            "MARGINALLY USABLE — works, but content quality and/or actions are shaky. "
            "Would not stake a demo solely on this URL without more hardening."
        )
    else:
        overall = (
            "NOT GOOD ENOUGH as an ideal LLM browser on this class of site yet — "
            "fix or actionability is too weak."
        )
    lines.append("OVERALL: " + overall)
    return "\n".join(lines)


def print_report(c: dict, trad: dict, agent: dict) -> None:
    print("\n" + "=" * 78)
    print("HARD-SITE BENCHMARK (no sugarcoating)")
    print(c["url"])
    print(c["why_this_site"])
    print("=" * 78)
    print("\nTRADITIONAL httpx+BS4")
    print(f"  error/status: {trad.get('error')} / {trad.get('status')}")
    print(f"  latency:      {trad.get('latency_ms')} ms")
    print(f"  raw HTML:     {trad.get('raw_html_tokens')} tokens")
    print(f"  visible text: {trad.get('text_tokens')} tokens")
    print(f"  structured:   {trad.get('structured_tokens')} tokens")
    print(f"  headings/links: {trad.get('heading_count')} / {trad.get('link_count')}")
    print(f"  title: {(trad.get('payload') or {}).get('title')}")

    print("\nAGENT BROWSER")
    print(f"  error:        {agent.get('error')}")
    print(f"  latency:      {agent.get('latency_ms')} ms")
    print(f"  final url:    {agent.get('final_url')}")
    print(f"  raw HTML:     {agent.get('raw_html_tokens')} tokens (after JS)")
    print(f"  body text:    {agent.get('text_tokens')} tokens")
    print(f"  observation:  {agent.get('observation_tokens')} tokens  << LLM feed")
    print(f"  headings/refs:{agent.get('heading_count')} / {agent.get('actionable_refs')}")
    print(f"  network:      {agent.get('network_requests')}")
    print(f"  summary:      {(agent.get('summary') or '')[:200]}")
    ar = agent.get("action_result")
    if ar:
        print(f"  click Issues: ok={ar.get('ok')} code={ar.get('error_code')} url={ar.get('url_after')}")

    print("\nPERCENTAGES")
    t = c["tokens"]
    print(
        f"  observation vs trad raw HTML: "
        f"{t.get('observation_as_pct_of_trad_raw_html')}% size "
        f"({t.get('observation_reduction_vs_trad_raw_pct')}% reduction)"
    )
    print(
        f"  observation vs agent raw HTML: "
        f"{t.get('observation_as_pct_of_agent_raw_html')}% size "
        f"({t.get('observation_reduction_vs_agent_raw_pct')}% reduction)"
    )
    print(
        f"  content signals: trad {c['content_signal_hit_rate_pct']['traditional']}% "
        f"vs agent {c['content_signal_hit_rate_pct']['agent']}%"
    )
    print(f"  found trad:  {c['content_signal_hit_rate_pct']['traditional_found']}")
    print(f"  found agent: {c['content_signal_hit_rate_pct']['agent_found']}")
    print(f"  speed: agent {c['latency_ms']['agent_vs_trad_multiplier']}x traditional")

    print("\nFAILURES / WEAKNESSES")
    for f in c["failures_and_weaknesses"] or ["(none flagged by heuristics)"]:
        print(f"  - {f}")

    print("\nBLUNT VERDICT")
    print(c["blunt_verdict"])
    print("=" * 78)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--out", default="data/benchmark_hard_site")
    args = ap.parse_args()
    url = args.url

    # Domain-specific content probes (what a competent agent should "notice")
    if "github.com" in url:
        signals = [
            "next.js",
            "vercel",
            "typescript",
            "issues",
            "pull requests",
            "star",
            "fork",
            "readme",
            "mit",
            "javascript",
        ]
    elif "reddit.com" in url:
        signals = ["reddit", "posts", "comment", "upvote", "join", "community"]
    else:
        signals = ["home", "login", "search", "menu", "about"]

    print("Traditional…")
    trad = await traditional(url)
    print("Agent (slow)…")
    agent = await agent_run(url)
    c = compare(url, trad, agent, signals)
    c["blunt_verdict"] = blunt_verdict(c, trad, agent)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "traditional.json").write_text(
        json.dumps(trad, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    (out / "agent.json").write_text(
        json.dumps(agent, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    (out / "comparison.json").write_text(
        json.dumps(c, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print_report(c, trad, agent)
    print(f"\nWrote {out.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
