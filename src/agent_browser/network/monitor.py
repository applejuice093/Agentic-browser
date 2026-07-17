"""XHR/Fetch/WebSocket capture, wait_for_api, GraphQL detection (M5)."""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import re
import time
import uuid
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from agent_browser.models.events import BrowserEvent, EventType
from agent_browser.models.network import NetworkRequest
from agent_browser.network.graphql import is_graphql_request, parse_graphql_payload

# Headers that should never be stored in clear text for agents by default
_SENSITIVE_HEADER_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "proxy-authorization",
        "x-api-key",
        "x-auth-token",
        "x-csrf-token",
    }
)

_DEFAULT_MAX_BODY = 64_000


def _mask_headers(headers: dict[str, str], *, mask_sensitive: bool = True) -> dict[str, str]:
    if not mask_sensitive:
        return dict(headers)
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in _SENSITIVE_HEADER_KEYS:
            out[k] = "***"
        else:
            out[k] = v
    return out


def _url_matches(url: str, pattern: str) -> bool:
    """Match URL against substring, glob, or regex (if pattern starts with re:)."""
    if pattern.startswith("re:"):
        return re.search(pattern[3:], url) is not None
    if any(ch in pattern for ch in "*?[]"):
        return fnmatch.fnmatch(url, pattern) or fnmatch.fnmatch(
            urlparse(url).path, pattern
        )
    return pattern in url


class NetworkMonitor:
    """
    Hooks Playwright network events for agent introspection.

    Captures request metadata + optional response bodies (size-capped).
    Detects GraphQL POSTs and emits ``api_call`` / ``network_error`` events
    when an event bus callback is provided.
    """

    def __init__(
        self,
        *,
        max_body_bytes: int = _DEFAULT_MAX_BODY,
        mask_sensitive_headers: bool = True,
        capture_response_body: bool = True,
        resource_types: set[str] | None = None,
    ) -> None:
        self.max_body_bytes = max_body_bytes
        self.mask_sensitive_headers = mask_sensitive_headers
        self.capture_response_body = capture_response_body
        # None = capture common XHR-like types + document; empty set = all
        self.resource_types = resource_types
        self.requests: list[NetworkRequest] = []
        self._by_id: dict[str, NetworkRequest] = {}
        self._attached = False
        self._page: Any = None
        self._event_emit: Callable[[BrowserEvent], Any] | None = None
        self._waiters: list[tuple[str, asyncio.Future[NetworkRequest]]] = []
        self._lock = asyncio.Lock()
        self._websocket_events: list[dict[str, Any]] = []

    @property
    def is_attached(self) -> bool:
        return self._attached

    def set_event_emitter(self, emit: Callable[[BrowserEvent], Any] | None) -> None:
        self._event_emit = emit

    async def attach(self, page: Any) -> None:
        """Subscribe to Playwright request/response/requestfailed events."""
        if self._attached and self._page is page:
            return
        if self._attached:
            await self.detach()
        self._page = page

        page.on("request", self._on_request)
        page.on("requestfailed", self._on_request_failed)

        async def _response_handler(response: Any) -> None:
            await self._on_response(response)

        page.on("response", _response_handler)
        # WebSocket frames (best-effort; API varies by Playwright version)
        try:
            page.on("websocket", self._on_websocket)
        except Exception:
            pass

        self._attached = True

    async def detach(self) -> None:
        # Playwright does not always support off(); clear refs
        self._page = None
        self._attached = False

    def clear(self) -> None:
        self.requests.clear()
        self._by_id.clear()
        self._websocket_events.clear()

    def list_requests(
        self,
        *,
        filter: str | None = None,  # noqa: A002
        method: str | None = None,
        status: int | None = None,
        graphql_only: bool = False,
        failed_only: bool = False,
    ) -> list[NetworkRequest]:
        items = list(self.requests)
        if filter is not None:
            items = [r for r in items if _url_matches(r.url, filter)]
        if method is not None:
            m = method.upper()
            items = [r for r in items if r.method.upper() == m]
        if status is not None:
            items = [r for r in items if r.response_status == status]
        if graphql_only:
            items = [r for r in items if r.is_graphql]
        if failed_only:
            items = [r for r in items if r.failed]
        return items

    def network_requests(
        self,
        *,
        filter: str | None = None,  # noqa: A002
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Design-report style: list of summary dicts."""
        return [r.to_summary() for r in self.list_requests(filter=filter, **kwargs)]

    def get(self, request_id: str) -> NetworkRequest | None:
        return self._by_id.get(request_id)

    async def wait_for_api(
        self,
        url_pattern: str,
        *,
        timeout_ms: int = 30_000,
        method: str | None = None,
        status: int | None = None,
        include_body: bool = True,
    ) -> NetworkRequest:
        """
        Wait until a matching request completes (or has failed).

        Matches existing log first, then waits for new traffic.
        """
        # Already captured?
        for req in reversed(self.requests):
            if self._matches_waiter(req, url_pattern, method=method, status=status):
                if include_body and req.response_body is None and not req.failed:
                    pass  # body may still be loading; prefer completed entries
                if req.response_status is not None or req.failed:
                    return req

        loop = asyncio.get_running_loop()
        future: asyncio.Future[NetworkRequest] = loop.create_future()
        self._waiters.append((url_pattern, future))
        # Store method/status on future for matching via closure
        future._ab_method = method  # type: ignore[attr-defined]
        future._ab_status = status  # type: ignore[attr-defined]

        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000.0)
        except TimeoutError as exc:
            from agent_browser.exceptions import NetworkTimeoutError

            raise NetworkTimeoutError(
                f"wait_for_api timed out after {timeout_ms}ms for pattern {url_pattern!r}"
            ) from exc
        finally:
            self._waiters = [(p, f) for p, f in self._waiters if f is not future]

    def _matches_waiter(
        self,
        req: NetworkRequest,
        pattern: str,
        *,
        method: str | None,
        status: int | None,
    ) -> bool:
        if not _url_matches(req.url, pattern):
            return False
        if method and req.method.upper() != method.upper():
            return False
        if status is not None and req.response_status != status:
            return False
        return True

    def _should_capture(self, resource_type: str | None, url: str = "") -> bool:
        if self.resource_types is not None and len(self.resource_types) == 0:
            return True
        url_l = (url or "").lower()
        if any(x in url_l for x in ("/api", "graphql", "/gql", ".json")):
            return True
        if self.resource_types is None:
            # Default: xhr/fetch/document/websocket/other interesting
            return (resource_type or "") in {
                "xhr",
                "fetch",
                "document",
                "websocket",
                "eventsource",
                "other",
            } or resource_type is None
        return (resource_type or "") in self.resource_types

    def _on_request(self, request: Any) -> None:
        try:
            rtype = request.resource_type
            url = request.url
            if not self._should_capture(rtype, url):
                return
            rid = self._request_id(request)
            headers = dict(request.headers)
            post = None
            try:
                post = request.post_data
            except Exception:
                post = None
            gql = is_graphql_request(
                url=request.url,
                method=request.method,
                headers=headers,
                post_data=post,
            )
            gql_meta = parse_graphql_payload(post) if gql else {}
            entry = NetworkRequest(
                id=rid,
                url=request.url,
                method=request.method,
                resource_type=rtype,
                headers=_mask_headers(headers, mask_sensitive=self.mask_sensitive_headers),
                post_data=self._truncate(post) if post else None,
                timestamp=time.time(),
                is_graphql=gql,
                graphql_operation=gql_meta.get("operation"),
                graphql_query_name=gql_meta.get("query_name"),
                frame_url=getattr(getattr(request, "frame", None), "url", None),
            )
            self._by_id[rid] = entry
            self.requests.append(entry)
        except Exception:
            return

    async def _on_response(self, response: Any) -> None:
        try:
            request = response.request
            rid = self._request_id(request)
            entry = self._by_id.get(rid)
            if entry is None:
                # Response without captured request — create minimal entry
                if not self._should_capture(request.resource_type):
                    url = request.url
                    if not any(x in url for x in ("/api", "graphql", "/gql", ".json")):
                        return
                headers = dict(request.headers)
                post = None
                try:
                    post = request.post_data
                except Exception:
                    pass
                gql = is_graphql_request(
                    url=request.url,
                    method=request.method,
                    headers=headers,
                    post_data=post,
                )
                gql_meta = parse_graphql_payload(post) if gql else {}
                entry = NetworkRequest(
                    id=rid,
                    url=request.url,
                    method=request.method,
                    resource_type=request.resource_type,
                    headers=_mask_headers(
                        headers, mask_sensitive=self.mask_sensitive_headers
                    ),
                    post_data=self._truncate(post) if post else None,
                    timestamp=time.time(),
                    is_graphql=gql,
                    graphql_operation=gql_meta.get("operation"),
                    graphql_query_name=gql_meta.get("query_name"),
                )
                self._by_id[rid] = entry
                self.requests.append(entry)

            entry.response_status = response.status
            try:
                entry.response_headers = _mask_headers(
                    dict(response.headers),
                    mask_sensitive=self.mask_sensitive_headers,
                )
            except Exception:
                pass
            entry.timing_ms = (time.time() - entry.timestamp) * 1000.0

            if self.capture_response_body:
                try:
                    # Prefer text; binary becomes placeholder
                    body = await response.text()
                    if len(body.encode("utf-8", errors="replace")) > self.max_body_bytes:
                        entry.response_body = body[: self.max_body_bytes]
                        entry.response_body_truncated = True
                    else:
                        entry.response_body = body
                except Exception:
                    try:
                        raw = await response.body()
                        digest = hashlib.sha256(raw).hexdigest()[:16]
                        entry.response_body = f"<binary {len(raw)} bytes sha256={digest}>"
                    except Exception:
                        entry.response_body = None

            await self._notify_waiters(entry)
            await self._emit_api_event(entry)
        except Exception:
            return

    def _on_request_failed(self, request: Any) -> None:
        try:
            rid = self._request_id(request)
            entry = self._by_id.get(rid)
            failure = None
            try:
                failure = request.failure
            except Exception:
                failure = None
            if entry is None:
                entry = NetworkRequest(
                    id=rid,
                    url=request.url,
                    method=request.method,
                    resource_type=request.resource_type,
                    timestamp=time.time(),
                    failed=True,
                    failure_text=str(failure) if failure else "requestfailed",
                )
                self._by_id[rid] = entry
                self.requests.append(entry)
            else:
                entry.failed = True
                entry.failure_text = str(failure) if failure else "requestfailed"

            # Notify waiters and emit error
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._notify_waiters(entry))
                loop.create_task(
                    self._emit(
                        BrowserEvent.make(
                            EventType.NETWORK_ERROR,
                            id=entry.id,
                            url=entry.url,
                            method=entry.method,
                            failure=entry.failure_text,
                        )
                    )
                )
            except RuntimeError:
                pass
        except Exception:
            return

    def _on_websocket(self, ws: Any) -> None:
        try:
            info = {"url": ws.url, "timestamp": time.time()}
            self._websocket_events.append(info)

            def _on_frame_sent(payload: Any) -> None:
                self._websocket_events.append(
                    {"url": ws.url, "direction": "sent", "payload": str(payload)[:500]}
                )

            def _on_frame_received(payload: Any) -> None:
                self._websocket_events.append(
                    {
                        "url": ws.url,
                        "direction": "received",
                        "payload": str(payload)[:500],
                    }
                )

            ws.on("framesent", _on_frame_sent)
            ws.on("framereceived", _on_frame_received)
        except Exception:
            return

    def list_websockets(self) -> list[dict[str, Any]]:
        return list(self._websocket_events)

    async def _notify_waiters(self, entry: NetworkRequest) -> None:
        completed: list[asyncio.Future[NetworkRequest]] = []
        for pattern, fut in list(self._waiters):
            if fut.done():
                completed.append(fut)
                continue
            method = getattr(fut, "_ab_method", None)
            status = getattr(fut, "_ab_status", None)
            if self._matches_waiter(entry, pattern, method=method, status=status):
                if entry.response_status is not None or entry.failed:
                    fut.set_result(entry)
                    completed.append(fut)
        if completed:
            self._waiters = [(p, f) for p, f in self._waiters if f not in completed]

    async def _emit_api_event(self, entry: NetworkRequest) -> None:
        # Emit for XHR/fetch/graphql-ish traffic
        rtype = entry.resource_type or ""
        if rtype not in ("xhr", "fetch", "other", "") and not entry.is_graphql:
            if "/api" not in entry.url and "graphql" not in entry.url.lower():
                return
        await self._emit(
            BrowserEvent.make(
                EventType.API_CALL,
                id=entry.id,
                url=entry.url,
                method=entry.method,
                status=entry.response_status,
                is_graphql=entry.is_graphql,
                graphql_operation=entry.graphql_operation,
                graphql_query_name=entry.graphql_query_name,
            )
        )

    async def _emit(self, event: BrowserEvent) -> None:
        if self._event_emit is None:
            return
        result = self._event_emit(event)
        if asyncio.iscoroutine(result):
            await result

    def _request_id(self, request: Any) -> str:
        # Prefer Playwright unique id when available
        try:
            uid = getattr(request, "guid", None) or id(request)
            return str(uid)
        except Exception:
            return str(uuid.uuid4())

    def _truncate(self, text: str | None) -> str | None:
        if text is None:
            return None
        raw = text.encode("utf-8", errors="replace")
        if len(raw) <= self.max_body_bytes:
            return text
        return text[: self.max_body_bytes]
