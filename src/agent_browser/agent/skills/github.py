"""
GitHub domain skill pack.

Coding agents visit GitHub constantly. Map intent → scoped find + URL outcomes.
This is a skill layer, not a hard dependency of the core browser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from agent_browser.agent.grounding import FindScope
from agent_browser.agent.outcome import OutcomeExpectation


@dataclass
class GitHubIntent:
    name: str
    role: str
    text: str
    scope: FindScope
    exact: bool
    expectation: OutcomeExpectation
    href_hint: str | None = None


_INTENTS: list[tuple[re.Pattern[str], GitHubIntent]] = [
    (
        re.compile(r"\bissues?\b", re.I),
        GitHubIntent(
            name="issues",
            role="link",
            text="Issues",
            scope=FindScope.NAV,
            exact=True,
            expectation=OutcomeExpectation(
                url_contains="/issues",
                require_navigation=True,
                timeout_ms=5_000,
            ),
            href_hint="/issues",
        ),
    ),
    (
        re.compile(r"\bpull requests?\b|\bprs?\b", re.I),
        GitHubIntent(
            name="pulls",
            role="link",
            text="Pull requests",
            scope=FindScope.NAV,
            exact=False,
            expectation=OutcomeExpectation(
                url_contains="/pulls",
                require_navigation=True,
                timeout_ms=5_000,
            ),
            href_hint="/pulls",
        ),
    ),
    (
        re.compile(r"\bactions\b", re.I),
        GitHubIntent(
            name="actions",
            role="link",
            text="Actions",
            scope=FindScope.NAV,
            exact=True,
            expectation=OutcomeExpectation(
                url_contains="/actions",
                require_navigation=True,
                timeout_ms=5_000,
            ),
            href_hint="/actions",
        ),
    ),
    (
        re.compile(r"\bcode\b", re.I),
        GitHubIntent(
            name="code",
            role="link",
            text="Code",
            scope=FindScope.NAV,
            exact=True,
            expectation=OutcomeExpectation(timeout_ms=1_000),
            href_hint=None,
        ),
    ),
    (
        re.compile(r"\bwiki\b", re.I),
        GitHubIntent(
            name="wiki",
            role="link",
            text="Wiki",
            scope=FindScope.NAV,
            exact=True,
            expectation=OutcomeExpectation(
                url_contains="/wiki", require_navigation=True, timeout_ms=5_000
            ),
            href_hint="/wiki",
        ),
    ),
    (
        re.compile(r"\bsecurity\b", re.I),
        GitHubIntent(
            name="security",
            role="link",
            text="Security",
            scope=FindScope.NAV,
            exact=True,
            expectation=OutcomeExpectation(
                url_contains="/security", require_navigation=True, timeout_ms=5_000
            ),
            href_hint="/security",
        ),
    ),
]


def is_github_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host == "github.com" or host.endswith(".github.com")


def resolve_intent(text: str) -> GitHubIntent | None:
    for pat, intent in _INTENTS:
        if pat.search(text or ""):
            return intent
    return None


async def github_goto_tab(page: Any, intent: GitHubIntent) -> dict[str, Any]:
    """
    Prefer direct URL navigation for repo tabs when on a repository page.
    More reliable than clicking ambiguous links (research: prefer high-level
    navigation when path is deterministic).
    """
    url = page.url
    # https://github.com/owner/repo[/...]
    m = re.match(r"(https?://github\.com/[^/]+/[^/]+)", url)
    if not m or not intent.href_hint:
        return {"ok": False, "reason": "not_on_repo_or_no_hint"}
    base = m.group(1).rstrip("/")
    target = base + intent.href_hint
    await page.goto(target)
    return {"ok": True, "url": target}
