"""GraphQL request detection helpers (M5)."""

from __future__ import annotations

import json
import re
from typing import Any


_OP_RE = re.compile(
    r"\b(query|mutation|subscription)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE | re.DOTALL,
)
_ANON_RE = re.compile(r"\b(query|mutation|subscription)\b\s*[{\(]", re.IGNORECASE)


def is_graphql_request(
    *,
    url: str,
    method: str,
    headers: dict[str, str] | None,
    post_data: str | None,
) -> bool:
    """Heuristic: URL path, content-type, or JSON body with query/mutation."""
    url_l = url.lower()
    if "graphql" in url_l or url_l.rstrip("/").endswith("/gql"):
        return True
    hdrs = {k.lower(): v for k, v in (headers or {}).items()}
    ctype = hdrs.get("content-type", "")
    if "graphql" in ctype:
        return True
    if method.upper() != "POST" or not post_data:
        return False
    try:
        body = json.loads(post_data)
    except (json.JSONDecodeError, TypeError):
        return "query" in post_data[:200] and "{" in post_data
    if isinstance(body, dict):
        if "query" in body or "mutation" in body:
            return True
        # batch
        if isinstance(body.get("query"), str):
            return True
    if isinstance(body, list) and body and isinstance(body[0], dict):
        return any("query" in item for item in body if isinstance(item, dict))
    return False


def parse_graphql_payload(post_data: str | None) -> dict[str, Any]:
    """
    Extract operation type and name from a GraphQL POST body.

    Returns keys: operation, query_name, variables (optional), raw_query (truncated).
    """
    result: dict[str, Any] = {
        "operation": None,
        "query_name": None,
        "variables": None,
        "raw_query": None,
    }
    if not post_data:
        return result
    try:
        body = json.loads(post_data)
    except (json.JSONDecodeError, TypeError):
        query = post_data
        result["raw_query"] = query[:500]
        m = _OP_RE.search(query) or _ANON_RE.search(query)
        if m:
            result["operation"] = m.group(1).lower()
            if m.lastindex and m.lastindex >= 2 and m.group(2):
                result["query_name"] = m.group(2)
        return result

    if isinstance(body, list) and body:
        body = body[0]
    if not isinstance(body, dict):
        return result

    query = body.get("query") or body.get("mutation") or ""
    if isinstance(query, str):
        result["raw_query"] = query[:500]
        m = _OP_RE.search(query)
        if m:
            result["operation"] = m.group(1).lower()
            result["query_name"] = m.group(2)
        else:
            m2 = _ANON_RE.search(query)
            if m2:
                result["operation"] = m2.group(1).lower()
        if body.get("operationName"):
            result["query_name"] = body["operationName"]
    if "variables" in body:
        result["variables"] = body["variables"]
    return result
