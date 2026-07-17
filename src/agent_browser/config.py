"""Runtime configuration for the agent browser."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrowserConfig(BaseSettings):
    """Environment-backed settings for browser sessions."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_BROWSER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    headless: bool = True
    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium"
    default_timeout_ms: int = Field(default=30_000, ge=0)
    slow_mo_ms: int = Field(default=0, ge=0)
    viewport_width: int = Field(default=1280, ge=1)
    viewport_height: int = Field(default=720, ge=1)
    user_agent: str | None = None
    locale: str = "en-US"
    respect_robots_txt: bool = True
