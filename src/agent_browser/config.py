"""Runtime configuration for the agent browser.

Settings are loaded from environment variables with the ``AGENT_BROWSER_``
prefix (and optionally from a local ``.env`` file). See ``.env.example``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrowserConfig(BaseSettings):
    """Environment-backed settings for browser sessions.

    All fields accept ``AGENT_BROWSER_<NAME>`` env vars (case-insensitive).
    Example: ``AGENT_BROWSER_HEADLESS=false``.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENT_BROWSER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    headless: bool = Field(
        default=True,
        description="Run Chromium/Firefox/WebKit without a visible window.",
    )
    browser_type: Literal["chromium", "firefox", "webkit"] = Field(
        default="chromium",
        description="Playwright browser engine to launch.",
    )
    default_timeout_ms: int = Field(
        default=30_000,
        ge=0,
        description="Default Playwright action/navigation timeout in milliseconds.",
    )
    slow_mo_ms: int = Field(
        default=0,
        ge=0,
        description="Artificial delay between Playwright operations (debugging).",
    )
    viewport_width: int = Field(default=1280, ge=1, description="Default viewport width.")
    viewport_height: int = Field(default=720, ge=1, description="Default viewport height.")
    user_agent: str | None = Field(
        default=None,
        description="Override User-Agent; None keeps the engine default.",
    )
    locale: str = Field(default="en-US", description="Browser locale (Accept-Language / Intl).")
    respect_robots_txt: bool = Field(
        default=True,
        description="When True, callers should honor robots.txt before autonomous crawls.",
    )
    # M8 humanization
    humanize: bool = Field(
        default=False,
        description="Enable humanized mouse paths and typing delays (M8).",
    )
    humanize_min_delay_ms: float = Field(
        default=30,
        ge=0,
        description="Minimum per-keystroke / micro-move delay when humanize is on.",
    )
    humanize_max_delay_ms: float = Field(
        default=120,
        ge=0,
        description="Maximum per-keystroke / micro-move delay when humanize is on.",
    )

    @model_validator(mode="after")
    def _check_humanize_range(self) -> BrowserConfig:
        if self.humanize_min_delay_ms > self.humanize_max_delay_ms:
            raise ValueError(
                "humanize_min_delay_ms must not exceed humanize_max_delay_ms "
                f"({self.humanize_min_delay_ms} > {self.humanize_max_delay_ms})"
            )
        return self
