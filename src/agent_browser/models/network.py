"""Network request / response models (M5)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NetworkRequest(BaseModel):
    """Captured HTTP(S) request/response pair for agent introspection."""

    id: str
    url: str
    method: str = "GET"
    resource_type: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    post_data: str | None = None
    timestamp: float = 0.0
    response_status: int | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: str | None = None
    response_body_truncated: bool = False
    timing_ms: float | None = None
    failed: bool = False
    failure_text: str | None = None
    is_graphql: bool = False
    graphql_operation: str | None = None
    graphql_query_name: str | None = None
    frame_url: str | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "method": self.method,
            "url": self.url,
            "status": self.response_status,
            "resource_type": self.resource_type,
            "is_graphql": self.is_graphql,
            "graphql_operation": self.graphql_operation,
            "graphql_query_name": self.graphql_query_name,
            "failed": self.failed,
        }
