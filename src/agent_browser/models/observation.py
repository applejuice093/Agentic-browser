"""Agent-native observation & action result schemas (compact, versioned)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


SCHEMA_VERSION = "1.0"


class ErrorCode(str, Enum):
    """Stable failure taxonomy for agent branching."""

    OK = "ok"
    ELEMENT_NOT_FOUND = "element_not_found"
    ELEMENT_STALE = "element_stale"
    ELEMENT_NOT_VISIBLE = "element_not_visible"
    ELEMENT_DISABLED = "element_disabled"
    TIMEOUT = "timeout"
    NAVIGATION_FAILED = "navigation_failed"
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_ERROR = "network_error"
    SNAPSHOT_FAILED = "snapshot_failed"
    INVALID_ARGS = "invalid_args"
    PAGE_CLOSED = "page_closed"
    CAPTCHA_SUSPECTED = "captcha_suspected"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class DetailLevel(str, Enum):
    """How much page state to include in an observation."""

    SPARSE = "sparse"  # interactive only, short text, no boxes
    NORMAL = "normal"  # interactive + headings + landmarks
    FULL = "full"  # full semantic tree (debug / resync)


class InteractiveRef(BaseModel):
    """Compact handle an LLM can click/type without CSS."""

    ref: int
    role: str | None = None
    name: str | None = None
    text: str | None = None
    tag: str | None = None
    value: str | None = None
    href: str | None = None
    visible: bool = True
    enabled: bool = True
    checked: bool | None = None
    placeholder: str | None = None
    # omitted by default in sparse mode
    box: dict[str, float] | None = None


class DiffSummary(BaseModel):
    added: int = 0
    removed: int = 0
    changed: int = 0
    url_changed: bool = False
    title_changed: bool = False
    added_refs: list[int] = Field(default_factory=list)
    removed_refs: list[int] = Field(default_factory=list)
    changed_refs: list[int] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return (
            self.added == 0
            and self.removed == 0
            and self.changed == 0
            and not self.url_changed
            and not self.title_changed
        )


class NetworkHint(BaseModel):
    """Lightweight network signal attached to a step."""

    url: str
    method: str = "GET"
    status: int | None = None
    is_graphql: bool = False
    graphql_query_name: str | None = None
    failed: bool = False


class Observation(BaseModel):
    """
    Default LLM-facing page state after navigate/action/observe.

    Designed to stay within a few thousand tokens on typical pages.
    """

    schema_version: str = SCHEMA_VERSION
    url: str = ""
    title: str = ""
    detail: DetailLevel = DetailLevel.NORMAL
    interactive: list[InteractiveRef] = Field(default_factory=list)
    headings: list[InteractiveRef] = Field(default_factory=list)
    diff: DiffSummary | None = None
    network: list[NetworkHint] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    scroll_position: float = 0.0
    element_total: int = 0
    interactive_total: int = 0
    truncated: bool = False
    approx_tokens: int = 0
    step: int = 0
    note: str | None = None
    # High-signal summary for marketing/SPA landings
    summary: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_llm_dict(self) -> dict[str, Any]:
        """Drop nulls / empty fields for cheaper prompts."""
        data = self.model_dump(mode="json", exclude_none=True)
        if data.get("diff") and not any(
            [
                data["diff"].get("added"),
                data["diff"].get("removed"),
                data["diff"].get("changed"),
                data["diff"].get("url_changed"),
                data["diff"].get("title_changed"),
            ]
        ):
            data.pop("diff", None)
        if not data.get("network"):
            data.pop("network", None)
        if not data.get("errors"):
            data.pop("errors", None)
        if not data.get("alerts"):
            data.pop("alerts", None)
        if not data.get("headings"):
            data.pop("headings", None)
        if not data.get("meta"):
            data.pop("meta", None)
        return data


class ActionResult(BaseModel):
    """Result of a single agent action — always returned, even on failure."""

    schema_version: str = SCHEMA_VERSION
    ok: bool
    action: str
    error_code: ErrorCode = ErrorCode.OK
    error_message: str | None = None
    elapsed_ms: float = 0.0
    target_ref: int | str | None = None
    navigated: bool = False
    url_before: str | None = None
    url_after: str | None = None
    observation: Observation | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_llm_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json", exclude_none=True)
        if data.get("observation"):
            # re-compact nested observation
            if self.observation is not None:
                data["observation"] = self.observation.to_llm_dict()
        if not data.get("extra"):
            data.pop("extra", None)
        return data


WaitKind = Literal[
    "timeout",
    "selector",
    "url",
    "text",
    "networkidle",
    "api",
    "load",
    "domcontentloaded",
]
