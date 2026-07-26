"""Map Graph failures to stable, client-safe application errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class GraphErrorDetails:
    code: str
    safe_message: str
    status_code: int
    request_id: str | None = None
    retry_after: str | None = None


class GraphError(RuntimeError):
    def __init__(self, details: GraphErrorDetails) -> None:
        super().__init__(details.safe_message)
        self.details = details
        self.code = details.code
        self.status_code = details.status_code
        self.request_id = details.request_id
        self.retry_after = details.retry_after


def map_graph_response(response: httpx.Response) -> GraphError:
    status_code = response.status_code
    graph_code = _graph_error_code(response)
    code = _internal_code(status_code, graph_code)
    request_id = (
        response.headers.get("request-id")
        or response.headers.get("client-request-id")
    )
    return GraphError(
        GraphErrorDetails(
            code=code,
            safe_message=_safe_message(code),
            status_code=status_code,
            request_id=request_id,
            retry_after=response.headers.get("Retry-After"),
        )
    )


def map_graph_transport_error(error: Exception) -> GraphError:
    code = (
        "GRAPH_REQUEST_TIMEOUT"
        if isinstance(error, httpx.TimeoutException)
        else "GRAPH_SERVICE_UNAVAILABLE"
    )
    return GraphError(
        GraphErrorDetails(
            code=code,
            safe_message=_safe_message(code),
            status_code=504 if code == "GRAPH_REQUEST_TIMEOUT" else 503,
        )
    )


def _graph_error_code(response: httpx.Response) -> str | None:
    try:
        payload: Any = response.json()
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    value = error.get("code")
    return value if isinstance(value, str) else None


def _internal_code(status_code: int, graph_code: str | None) -> str:
    normalized = (graph_code or "").lower()
    if status_code == 401:
        return "GRAPH_AUTHENTICATION_FAILED"
    if status_code == 403:
        if "consent" in normalized:
            return "GRAPH_ADMIN_CONSENT_REQUIRED"
        return "GRAPH_AUTHORIZATION_FAILED"
    if status_code == 404:
        return "GRAPH_RESOURCE_NOT_FOUND"
    if status_code == 409:
        return "GRAPH_CONFLICT"
    if status_code == 413:
        return "GRAPH_PAYLOAD_TOO_LARGE"
    if status_code == 429:
        return "GRAPH_RATE_LIMITED"
    if status_code in {500, 502, 503, 504}:
        return "GRAPH_SERVICE_UNAVAILABLE"
    return "GRAPH_UNKNOWN_ERROR"


def _safe_message(code: str) -> str:
    messages = {
        "GRAPH_AUTHENTICATION_FAILED": (
            "Microsoft Graph authentication failed."
        ),
        "GRAPH_AUTHORIZATION_FAILED": (
            "Microsoft Graph denied the requested operation."
        ),
        "GRAPH_ADMIN_CONSENT_REQUIRED": (
            "Microsoft Graph administrator consent is required."
        ),
        "GRAPH_RATE_LIMITED": (
            "Microsoft Graph temporarily limited request throughput."
        ),
        "GRAPH_REQUEST_TIMEOUT": "The Microsoft Graph request timed out.",
        "GRAPH_RESOURCE_NOT_FOUND": (
            "The requested Microsoft Graph resource was not found."
        ),
        "GRAPH_CONFLICT": (
            "Microsoft Graph reported a conflicting remote change."
        ),
        "GRAPH_PAYLOAD_TOO_LARGE": (
            "The Microsoft Graph payload is too large."
        ),
        "GRAPH_SERVICE_UNAVAILABLE": (
            "Microsoft Graph is temporarily unavailable."
        ),
        "GRAPH_UNKNOWN_ERROR": "The Microsoft Graph request failed.",
    }
    return messages[code]
