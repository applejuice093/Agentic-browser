"""Grounding, outcome verification, challenge detection tests."""

from __future__ import annotations

import pytest

from agent_browser import Browser, ErrorCode
from agent_browser.agent.challenge import PageGate, classify_page_text
from agent_browser.agent.grounding import FindScope, best_elements
from agent_browser.agent.outcome import OutcomeExpectation, expectation_for_intent
from agent_browser.models.element import Element


def test_classify_js_challenge_reddit_style():
    r = classify_page_text(
        url="https://www.reddit.com/r/x/?js_challenge=1&token=abc",
        title="Reddit - Please wait for verification",
        body_text="Please wait for verification",
    )
    assert r.gate == PageGate.JS_CHALLENGE
    assert r.is_blocked


def test_classify_open_page():
    r = classify_page_text(
        url="https://github.com/vercel/next.js",
        title="GitHub - vercel/next.js",
        body_text="The React Framework Next.js stars forks Issues Pull requests",
    )
    assert r.gate in (PageGate.OPEN, PageGate.UNKNOWN)
    assert not r.is_blocked or r.gate == PageGate.OPEN


def test_grounding_prefers_nav_issues_over_commit_body():
    els = [
        Element(
            id=1,
            role="link",
            type="a",
            text="Issues",
            visible=True,
            enabled=True,
            attributes={"href": "/vercel/next.js/issues"},
        ),
        Element(
            id=2,
            role="link",
            type="a",
            text="Fix issues with build",
            name="Long PR body mentioning issues multiple times " * 5,
            visible=True,
            enabled=True,
            attributes={"href": "/vercel/next.js/pull/123"},
        ),
        Element(
            id=3,
            role="link",
            type="a",
            text="issue #99",
            visible=True,
            enabled=True,
            attributes={"href": "/vercel/next.js/issues/99"},
        ),
    ]
    best = best_elements(
        els, role="link", text="Issues", exact=True, scope=FindScope.NAV, min_score=1.0
    )
    assert best
    assert best[0].id == 1
    assert best[0].attributes["href"].endswith("/issues")


def test_expectation_for_issues_intent():
    exp = expectation_for_intent("open issues tab")
    assert exp is not None
    assert exp.url_contains == "/issues"
    assert exp.require_navigation is True


@pytest.mark.asyncio
async def test_github_click_text_issues_outcome():
    """Live: must land on /issues, not false-ok on same URL."""
    async with Browser(headless=True) as browser:
        agent = await browser.open_agent(
            "https://github.com/vercel/next.js",
            settle_budget_ms=12_000,
            max_tokens=1800,
        )
        # challenge check
        obs = await agent.observe(prepare=False)
        if obs.page_gate and obs.page_gate not in ("open", "cookie_wall", "unknown"):
            pytest.skip(f"blocked by gate {obs.page_gate}")

        result = await agent.click_text("Issues", role="link", scope="nav", intent="issues")
        assert result.ok, result.error_message
        assert result.outcome_verified is True
        assert "/issues" in (result.url_after or "")
        assert result.error_code == ErrorCode.OK


@pytest.mark.asyncio
async def test_false_match_without_skill_fails_outcome():
    """Clicking a bad ref that does not navigate should fail when expect is set."""
    async with Browser(headless=True) as browser:
        page = await browser.set_content(
            """
            <html><body>
              <a href="#nope">Issues mentioned in long text here</a>
              <nav><a id="real" href="/app/issues">Issues</a></nav>
            </body></html>
            """
        )
        # Use about:blank base — relative /app/issues won't navigate host;
        # instead test expectation failure on hash link click via raw click+expect
        agent = page.as_agent(auto_settle=False)
        await agent.observe(prepare=False)
        # force click first link with issues expectation — should not meet /issues path
        els = page.last_snapshot.elements if page.last_snapshot else []
        bad = next(e for e in els if e.attributes.get("href") == "#nope")
        res = await agent.click(
            bad.id,
            expect=OutcomeExpectation(
                url_contains="/issues", require_navigation=True, timeout_ms=800
            ),
            observe=False,
        )
        assert res.ok is False
        assert res.error_code == ErrorCode.OUTCOME_NOT_MET
        assert res.outcome_verified is False
