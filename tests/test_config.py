"""Config loading tests (no Playwright / network)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_browser.config import BrowserConfig


def test_default_config():
    cfg = BrowserConfig()
    assert cfg.headless is True
    assert cfg.browser_type == "chromium"
    assert cfg.default_timeout_ms == 30_000
    assert cfg.slow_mo_ms == 0
    assert cfg.viewport_width == 1280
    assert cfg.viewport_height == 720
    assert cfg.user_agent is None
    assert cfg.locale == "en-US"
    assert cfg.respect_robots_txt is True
    assert cfg.humanize is False


def test_config_accepts_overrides():
    cfg = BrowserConfig(
        headless=False,
        browser_type="firefox",
        default_timeout_ms=5_000,
        viewport_width=800,
        viewport_height=600,
        humanize=True,
        humanize_min_delay_ms=10,
        humanize_max_delay_ms=50,
    )
    assert cfg.headless is False
    assert cfg.browser_type == "firefox"
    assert cfg.default_timeout_ms == 5_000
    assert cfg.viewport_width == 800
    assert cfg.humanize is True
    assert cfg.humanize_min_delay_ms == 10


def test_config_rejects_invalid_browser_type():
    with pytest.raises(ValidationError):
        BrowserConfig(browser_type="netscape")  # type: ignore[arg-type]


def test_config_rejects_negative_timeout():
    with pytest.raises(ValidationError):
        BrowserConfig(default_timeout_ms=-1)


def test_config_reads_env_prefix(monkeypatch):
    monkeypatch.setenv("AGENT_BROWSER_HEADLESS", "false")
    monkeypatch.setenv("AGENT_BROWSER_BROWSER_TYPE", "webkit")
    monkeypatch.setenv("AGENT_BROWSER_DEFAULT_TIMEOUT_MS", "12000")
    cfg = BrowserConfig()
    assert cfg.headless is False
    assert cfg.browser_type == "webkit"
    assert cfg.default_timeout_ms == 12_000
