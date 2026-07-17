"""Config loading tests."""

from agent_browser.config import BrowserConfig


def test_default_config():
    cfg = BrowserConfig()
    assert cfg.headless is True
    assert cfg.browser_type == "chromium"
    assert cfg.default_timeout_ms == 30_000
