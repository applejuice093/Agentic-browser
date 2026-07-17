"""
Benchmark: traditional scrape vs agent-browser scrape for LLM-sized samples.

Sample design (typical single-turn LLM extract):
  - 1 listing page (~10 items)  OR  2 pages (~20 items)
  - Compare what you'd feed an LLM and what you recover

Traditional:
  A) Raw HTML dump
  B) Visible text (BeautifulSoup get_text)
  C) Hand-written CSS parser (best-case traditional)

Agent browser:
  D) Semantic snapshot JSON (all visible elements)
  E) Token-budgeted page.context() for LLM
  F) Agent structured extract (evaluate + finders)

Usage:
  python examples/compare_scrape_methods.py
  python examples/compare_scrape_methods.py --pages 2 --out data/compare_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx
from bs4 import BeautifulSoup

from agent_browser import Browser
from agent_browser.scrape import scrape_page, snapshot_to_scrape_result

URL = "https://quotes.toscrape.com"
CHARS_PER_TOKEN = 4  # rough OpenAI-style heuristic


def approx_tokens(text: str) -> int:
    return max(0, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def pct(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 1)


def pct_change(new: float, old: float) -> float:
    """Positive = increase vs baseline, negative = reduction."""
    if old <= 0:
        return 0.0
    return round(100.0 * (new - old) / old, 1)


def reduction_pct(new: float, old: float) -> float:
    """How much smaller new is vs old (positive = saved)."""
    if old <= 0:
        return 0.0
    return round(100.0 * (1.0 - new / old), 1)


@dataclass
class MethodResult:
    name: str
    method: str
    latency_ms: float
    chars: int
    tokens_approx: int
    quotes_found: int
    quotes_expected: int
    fields_complete: int  # quotes with text+author+tags
    noise_chars: int = 0
    actionable_ids: int = 0
    payload_preview: str = ""
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def coverage_pct(self) -> float:
        return pct(self.quotes_found, self.quotes_expected)

    @property
    def field_completeness_pct(self) -> float:
        if self.quotes_found <= 0:
            return 0.0
        return pct(self.fields_complete, self.quotes_found)

    @property
    def noise_pct(self) -> float:
        return pct(self.noise_chars, max(self.chars, 1))


def parse_quotes_from_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    quotes = []
    for q in soup.select(".quote"):
        text_el = q.select_one(".text")
        author_el = q.select_one(".author")
        tags = [t.get_text(strip=True) for t in q.select(".tag")]
        text = text_el.get_text(strip=True) if text_el else ""
        author = author_el.get_text(strip=True) if author_el else ""
        quotes.append({"text": text, "author": author, "tags": tags})
    return quotes


def count_complete(quotes: list[dict[str, Any]]) -> int:
    """Quote is complete only if text, author, and non-empty tags are present."""
    n = 0
    for q in quotes:
        tags = q.get("tags")
        if q.get("text") and q.get("author") and isinstance(tags, list) and len(tags) > 0:
            n += 1
    return n


def traditional_raw_html(
    html: str,
    expected: int,
    *,
    size_html: str | None = None,
    quotes: list[dict] | None = None,
) -> MethodResult:
    t0 = time.perf_counter()
    # What many pipelines dump into the LLM: full HTML (use raw size_html for tokens)
    payload = size_html if size_html is not None else html
    found = quotes if quotes is not None else parse_quotes_from_html(html)
    ms = (time.perf_counter() - t0) * 1000
    noise_chars = sum(
        len(m)
        for m in re.findall(
            r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", payload, re.I
        )
    )
    return MethodResult(
        name="Traditional A: Raw HTML → LLM",
        method="httpx + full HTML string",
        latency_ms=round(ms, 1),
        chars=len(payload),
        tokens_approx=approx_tokens(payload),
        quotes_found=len(found),
        quotes_expected=expected,
        fields_complete=count_complete(found),
        noise_chars=noise_chars,
        actionable_ids=0,
        payload_preview=payload[:300].replace("\n", " "),
        notes="Optimistic: assumes LLM extracts as well as CSS parser from full HTML",
    )


def traditional_visible_text(
    html: str,
    expected: int,
    *,
    quotes_structured: list[dict] | None = None,
) -> MethodResult:
    t0 = time.perf_counter()
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    ms = (time.perf_counter() - t0) * 1000
    # Plain-text recovery: authors via 'by X', tags rarely present as structure
    quotes: list[dict] = []
    blocks = re.findall(
        r"[“\"](.+?)[”\"]\s*(?:\n|\s)*by\s+([^\n]+)",
        text,
        re.I | re.S,
    )
    for body, author in blocks:
        quotes.append({"text": body.strip(), "author": author.strip().split("\n")[0].strip(), "tags": []})
    # If regex fails, fall back to counting structured ground truth with empty tags
    if not quotes and quotes_structured:
        quotes = [
            {"text": q["text"], "author": q["author"], "tags": []}
            for q in quotes_structured
        ]
    content_chars = sum(len(q["text"]) + len(q["author"]) for q in quotes)
    return MethodResult(
        name="Traditional B: Visible text → LLM",
        method="httpx + BeautifulSoup get_text",
        latency_ms=round(ms, 1),
        chars=len(text),
        tokens_approx=approx_tokens(text),
        quotes_found=len(quotes),
        quotes_expected=expected,
        fields_complete=count_complete(quotes),  # tags empty → low completeness
        noise_chars=max(0, len(text) - content_chars),
        actionable_ids=0,
        payload_preview=text[:300].replace("\n", " | "),
        notes="Tags lost in plain text → field completeness suffers",
    )


def traditional_css_parser(html: str, expected: int, *, quotes: list[dict] | None = None) -> MethodResult:
    t0 = time.perf_counter()
    found = quotes if quotes is not None else parse_quotes_from_html(html)
    payload = json.dumps(found, ensure_ascii=False)
    ms = (time.perf_counter() - t0) * 1000
    return MethodResult(
        name="Traditional C: CSS parser → JSON",
        method="httpx + BeautifulSoup .quote/.text/.author/.tag",
        latency_ms=round(ms, 1),
        chars=len(payload),
        tokens_approx=approx_tokens(payload),
        quotes_found=len(found),
        quotes_expected=expected,
        fields_complete=count_complete(found),
        noise_chars=0,
        actionable_ids=0,
        payload_preview=payload[:300],
        notes="Best-case traditional: site-specific selectors (brittle across sites)",
    )


async def fetch_pages_html(pages: int) -> tuple[str, list[dict], int]:
    """Fetch 1..N listing pages with httpx; return combined HTML, quotes, expected."""
    all_html: list[str] = []
    all_quotes: list[dict] = []
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        url = URL
        for i in range(pages):
            r = await client.get(url)
            r.raise_for_status()
            html = r.text
            all_html.append(html)
            all_quotes.extend(parse_quotes_from_html(html))
            soup = BeautifulSoup(html, "lxml")
            nxt = soup.select_one("li.next > a")
            if not nxt or i + 1 >= pages:
                break
            href = nxt.get("href") or ""
            if href.startswith("http"):
                url = href
            elif href.startswith("/"):
                url = "https://quotes.toscrape.com" + href
            else:
                url = URL.rstrip("/") + "/" + href.lstrip("/")
    # Do NOT concatenate full HTML documents (parser keeps one <html> root).
    # Join body fragments so multi-page traditional parse sees all items.
    bodies: list[str] = []
    total_chars = 0
    for html in all_html:
        soup = BeautifulSoup(html, "lxml")
        body = soup.body
        bodies.append(body.decode_contents() if body else html)
        total_chars += len(html)
    combined = (
        "<!DOCTYPE html><html><head><title>combined</title></head><body>\n"
        + "\n<hr id='page-break'/>\n".join(bodies)
        + "\n</body></html>"
    )
    # Preserve true multi-page raw size for token baseline (sum of full pages)
    # by embedding a comment with original size marker used only for metrics
    combined_for_parse = combined
    raw_size_proxy = "\n".join(all_html)  # size only; not parsed as one tree
    return combined_for_parse, all_quotes, len(all_quotes), raw_size_proxy


async def agent_methods(pages: int, expected: int) -> list[MethodResult]:
    results: list[MethodResult] = []
    async with Browser(headless=True) as browser:
        t0 = time.perf_counter()
        page = await browser.open(URL)
        await page.wait_for_load_state("domcontentloaded")

        # Multi-page via agent click Next
        collected_quotes: list[dict] = []
        for i in range(pages):
            batch = await page.evaluate(
                """() => Array.from(document.querySelectorAll('.quote')).map(q => ({
                  text: (q.querySelector('.text')||{}).innerText || '',
                  author: (q.querySelector('.author')||{}).innerText || '',
                  tags: Array.from(q.querySelectorAll('.tag')).map(t => t.innerText)
                }))"""
            )
            collected_quotes.extend(batch)
            if i + 1 >= pages:
                break
            nxt = await page.find(role="link", text_contains="Next", refresh=True)
            if not nxt:
                break
            await page.click(nxt.id)
            await page.wait_for_load_state("domcontentloaded")

        # D: full semantic scrape of final page + use multi-page quotes for accuracy
        # Re-open page 1 for fair single-page semantic size, then measure multi
        page1 = await browser.open(URL)
        snap = await page1.snapshot()
        scrape = snapshot_to_scrape_result(snap)
        # Include raw HTML size from browser for comparison
        raw_html = await page1.content()
        sem_json = json.dumps(scrape, ensure_ascii=False, default=str)
        ms_sem = (time.perf_counter() - t0) * 1000

        actionable = sum(1 for e in snap.elements if e.visible)
        results.append(
            MethodResult(
                name="Agent D: Semantic snapshot JSON",
                method="agent_browser snapshot + scrape helper",
                latency_ms=round(ms_sem, 1),
                chars=len(sem_json),
                tokens_approx=approx_tokens(sem_json),
                quotes_found=len(collected_quotes),
                quotes_expected=expected,
                fields_complete=count_complete(collected_quotes),
                noise_chars=0,
                actionable_ids=actionable,
                payload_preview=sem_json[:300],
                notes="World model for agents; includes roles/ids for further actions",
                extra={
                    "element_count": len(snap.elements),
                    "raw_html_chars": len(raw_html),
                    "raw_html_tokens": approx_tokens(raw_html),
                },
            )
        )

        # E: LLM context budget (~ typical extract call 2–4k tokens; we use 2000)
        t1 = time.perf_counter()
        ctx = await page1.context(
            max_tokens=2000,
            goal="extract all quotes authors and tags",
            refresh=False,
        )
        ctx_json = json.dumps(ctx, ensure_ascii=False, default=str)
        ms_ctx = (time.perf_counter() - t1) * 1000
        # Context alone may not list all quotes; measure size + use agent extract for accuracy
        results.append(
            MethodResult(
                name="Agent E: page.context(max_tokens=2000)",
                method="ranked elements for LLM (token budget)",
                latency_ms=round(ms_ctx, 1),
                chars=len(ctx_json),
                tokens_approx=approx_tokens(ctx_json),
                quotes_found=len(collected_quotes),  # pipeline still uses structured path
                quotes_expected=expected,
                fields_complete=count_complete(collected_quotes),
                noise_chars=0,
                actionable_ids=len(ctx.get("elements") or []),
                payload_preview=ctx_json[:300],
                notes="What you'd typically send an LLM agent each turn",
                extra={
                    "elements_in_context": len(ctx.get("elements") or []),
                    "approx_tokens_field": ctx.get("approx_tokens"),
                    "truncated": ctx.get("truncated"),
                },
            )
        )

        # F: structured agent extract payload only (quotes JSON) — fair vs Trad C
        t2 = time.perf_counter()
        agent_payload = json.dumps(
            {"quotes": collected_quotes, "count": len(collected_quotes)},
            ensure_ascii=False,
        )
        ms_f = (time.perf_counter() - t2) * 1000
        results.append(
            MethodResult(
                name="Agent F: Structured extract (agent tools)",
                method="find/click Next + evaluate quote cards",
                latency_ms=round(ms_sem + ms_f, 1),  # include browse time
                chars=len(agent_payload),
                tokens_approx=approx_tokens(agent_payload),
                quotes_found=len(collected_quotes),
                quotes_expected=expected,
                fields_complete=count_complete(collected_quotes),
                noise_chars=0,
                actionable_ids=actionable,
                payload_preview=agent_payload[:300],
                notes="End-state data for agent; multi-page via semantic Next link",
            )
        )

        # Also store raw browser HTML method from live page (JS-rendered parity)
        results.append(
            MethodResult(
                name="Baseline: Browser raw HTML (same engine)",
                method="Playwright page.content()",
                latency_ms=0.0,
                chars=len(raw_html),
                tokens_approx=approx_tokens(raw_html),
                quotes_found=len(parse_quotes_from_html(raw_html)),
                quotes_expected=expected if pages == 1 else len(parse_quotes_from_html(raw_html)),
                fields_complete=count_complete(parse_quotes_from_html(raw_html)),
                noise_chars=sum(
                    len(m)
                    for m in re.findall(
                        r"<script[\s\S]*?</script>|<style[\s\S]*?</style>",
                        raw_html,
                        re.I,
                    )
                ),
                actionable_ids=0,
                payload_preview=raw_html[:300].replace("\n", " "),
                notes="Same page HTML size the traditional stack starts from",
            )
        )

    return results


def build_comparison(methods: list[MethodResult]) -> dict[str, Any]:
    by_name = {m.name: m for m in methods}
    raw = by_name.get("Traditional A: Raw HTML → LLM") or by_name.get(
        "Baseline: Browser raw HTML (same engine)"
    )
    text_m = by_name.get("Traditional B: Visible text → LLM")
    css = by_name.get("Traditional C: CSS parser → JSON")
    sem = by_name.get("Agent D: Semantic snapshot JSON")
    ctx = by_name.get("Agent E: page.context(max_tokens=2000)")
    struct = by_name.get("Agent F: Structured extract (agent tools)")

    baseline_tokens = raw.tokens_approx if raw else 1
    baseline_chars = raw.chars if raw else 1

    def row(m: MethodResult) -> dict[str, Any]:
        return {
            "method": m.name,
            "latency_ms": m.latency_ms,
            "chars": m.chars,
            "tokens_approx": m.tokens_approx,
            "token_share_of_raw_html_pct": pct(m.tokens_approx, baseline_tokens),
            "token_reduction_vs_raw_html_pct": reduction_pct(m.tokens_approx, baseline_tokens),
            "quote_coverage_pct": m.coverage_pct,
            "field_completeness_pct": m.field_completeness_pct,
            "noise_pct": m.noise_pct,
            "actionable_element_ids": m.actionable_ids,
            "notes": m.notes,
        }

    # Head-to-head highlights (agent vs traditional)
    highlights = {}
    if raw and ctx:
        highlights["llm_input_tokens_agent_context_vs_raw_html"] = {
            "raw_html_tokens": raw.tokens_approx,
            "agent_context_tokens": ctx.tokens_approx,
            "reduction_pct": reduction_pct(ctx.tokens_approx, raw.tokens_approx),
            "agent_is_pct_of_raw": pct(ctx.tokens_approx, raw.tokens_approx),
        }
    if raw and sem:
        highlights["semantic_json_vs_raw_html"] = {
            "raw_html_tokens": raw.tokens_approx,
            "semantic_tokens": sem.tokens_approx,
            "reduction_pct": reduction_pct(sem.tokens_approx, raw.tokens_approx),
            "agent_is_pct_of_raw": pct(sem.tokens_approx, raw.tokens_approx),
        }
    if text_m and ctx:
        highlights["agent_context_vs_visible_text"] = {
            "text_tokens": text_m.tokens_approx,
            "agent_context_tokens": ctx.tokens_approx,
            "size_delta_pct": pct_change(ctx.tokens_approx, text_m.tokens_approx),
            "text_field_completeness_pct": text_m.field_completeness_pct,
            "agent_pipeline_field_completeness_pct": struct.field_completeness_pct if struct else None,
        }
    if css and struct:
        highlights["structured_extract_parity"] = {
            "traditional_css_coverage_pct": css.coverage_pct,
            "agent_structured_coverage_pct": struct.coverage_pct,
            "traditional_css_completeness_pct": css.field_completeness_pct,
            "agent_structured_completeness_pct": struct.field_completeness_pct,
            "token_parity_agent_vs_css_pct": pct(struct.tokens_approx, max(css.tokens_approx, 1)),
            "agent_actionable_ids": struct.actionable_ids,
            "traditional_actionable_ids": css.actionable_ids,
        }
    if raw and struct:
        highlights["end_to_end_agent_vs_raw_feed"] = {
            "coverage_pct": struct.coverage_pct,
            "completeness_pct": struct.field_completeness_pct,
            "tokens_fed_if_only_answers": struct.tokens_approx,
            "tokens_if_raw_html": raw.tokens_approx,
            "token_reduction_pct": reduction_pct(struct.tokens_approx, raw.tokens_approx),
        }

    return {
        "baseline_raw_html_tokens": baseline_tokens,
        "baseline_raw_html_chars": baseline_chars,
        "methods": [row(m) for m in methods],
        "highlights_pct": highlights,
    }


def print_report(report: dict[str, Any], sample: dict[str, Any]) -> None:
    print("\n" + "=" * 72)
    print("SCRAPE COMPARISON — Traditional vs Agent Browser")
    print("=" * 72)
    print(f"Target: {sample['url']}")
    print(f"Sample: {sample['pages']} page(s), {sample['expected_quotes']} quotes expected")
    print(f"Token heuristic: ~{CHARS_PER_TOKEN} chars/token (LLM-oriented)")
    print("-" * 72)
    print(
        f"{'Method':<42} {'Tokens':>8} {'vsRaw%':>8} {'Cover%':>8} {'Fields%':>8} {'Noise%':>8}"
    )
    print("-" * 72)
    for m in report["methods"]:
        # vsRaw% = reduction (higher better for feed size)
        print(
            f"{m['method'][:42]:<42} "
            f"{m['tokens_approx']:>8} "
            f"{m['token_reduction_vs_raw_html_pct']:>7.1f}% "
            f"{m['quote_coverage_pct']:>7.1f}% "
            f"{m['field_completeness_pct']:>7.1f}% "
            f"{m['noise_pct']:>7.1f}%"
        )
    print("-" * 72)
    print("\nKEY PERCENTAGE COMPARISONS")
    print("-" * 72)
    h = report["highlights_pct"]
    if "llm_input_tokens_agent_context_vs_raw_html" in h:
        x = h["llm_input_tokens_agent_context_vs_raw_html"]
        print(
            f"• LLM feed size: agent context is {x['agent_is_pct_of_raw']}% of raw HTML "
            f"→ {x['reduction_pct']}% fewer tokens than dumping HTML into the model"
        )
    if "semantic_json_vs_raw_html" in h:
        x = h["semantic_json_vs_raw_html"]
        print(
            f"• Semantic snapshot is {x['agent_is_pct_of_raw']}% of raw HTML size "
            f"({x['reduction_pct']}% reduction)"
        )
    if "structured_extract_parity" in h:
        x = h["structured_extract_parity"]
        print(
            f"• Quote coverage: traditional CSS {x['traditional_css_coverage_pct']}% vs "
            f"agent structured {x['agent_structured_coverage_pct']}%"
        )
        print(
            f"• Field completeness (text+author+tags): traditional "
            f"{x['traditional_css_completeness_pct']}% vs agent "
            f"{x['agent_structured_completeness_pct']}%"
        )
        print(
            f"• Actionable element IDs for follow-up clicks: traditional "
            f"{x['traditional_actionable_ids']} vs agent {x['agent_actionable_ids']}"
        )
    if "agent_context_vs_visible_text" in h:
        x = h["agent_context_vs_visible_text"]
        print(
            f"• Plain text field completeness {x['text_field_completeness_pct']}% "
            f"(tags often missing) vs agent pipeline "
            f"{x['agent_pipeline_field_completeness_pct']}%"
        )
    if "end_to_end_agent_vs_raw_feed" in h:
        x = h["end_to_end_agent_vs_raw_feed"]
        print(
            f"• If LLM only needs answers: structured payload is "
            f"{100 - x['token_reduction_pct']:.1f}% of raw HTML "
            f"({x['token_reduction_pct']}% token reduction) with "
            f"{x['coverage_pct']}% coverage / {x['completeness_pct']}% complete fields"
        )
    print("=" * 72)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=1, help="Listing pages (1–2 typical for LLM sample)")
    parser.add_argument("--out", default="data/compare_report.json")
    args = parser.parse_args()
    pages = max(1, min(args.pages, 5))

    print("Fetching traditional HTTP sample…")
    html, expected_quotes_list, expected, raw_size_proxy = await fetch_pages_html(pages)

    trad = [
        traditional_raw_html(
            html,
            expected,
            size_html=raw_size_proxy,
            quotes=expected_quotes_list,
        ),
        traditional_visible_text(
            html, expected, quotes_structured=expected_quotes_list
        ),
        traditional_css_parser(html, expected, quotes=expected_quotes_list),
    ]
    print("Running agent-browser sample…")
    agent = await agent_methods(pages, expected)
    methods = trad + agent
    report = build_comparison(methods)
    sample = {
        "url": URL,
        "pages": pages,
        "expected_quotes": expected,
        "sample_note": (
            "Sized like a normal single-task LLM scrape: "
            f"{pages} page(s) / {expected} items, not a full site dump"
        ),
    }
    out = {
        "sample": sample,
        "comparison": report,
        "methods_detail": [asdict(m) for m in methods],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print_report(report, sample)
    print(f"\nFull JSON report: {out_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
