"""Domain skill packs for high-traffic agent destinations."""

from agent_browser.agent.skills.github import (
    GitHubIntent,
    github_goto_tab,
    is_github_url,
    resolve_intent,
)

__all__ = [
    "GitHubIntent",
    "github_goto_tab",
    "is_github_url",
    "resolve_intent",
]
