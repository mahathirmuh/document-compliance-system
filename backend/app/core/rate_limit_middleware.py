"""Route-aware Redis rate limiting for sensitive and expensive API actions."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.exceptions import ApplicationError
from app.services.security.rate_limiter import RateLimitRule, RedisRateLimiter


@dataclass(frozen=True, slots=True)
class RouteRateLimit:
    """One method/path matcher and its bounded Redis rule."""

    methods: frozenset[str]
    path_pattern: re.Pattern[str]
    rule: RateLimitRule

    @classmethod
    def compile(
        cls,
        *,
        methods: set[str] | frozenset[str],
        path_pattern: str,
        name: str,
        limit: int,
        window_seconds: int,
    ) -> RouteRateLimit:
        return cls(
            methods=frozenset(method.upper() for method in methods),
            path_pattern=re.compile(path_pattern),
            rule=RateLimitRule(
                name=name,
                limit=limit,
                window_seconds=window_seconds,
            ),
        )

    def matches(self, request: Request) -> bool:
        return (
            request.method.upper() in self.methods
            and self.path_pattern.fullmatch(request.url.path) is not None
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply the first matching route rule without storing raw credentials."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: RedisRateLimiter,
        route_limits: tuple[RouteRateLimit, ...],
    ) -> None:
        super().__init__(app)
        self.limiter = limiter
        self.route_limits = route_limits

    async def dispatch(self, request: Request, call_next) -> Response:
        route_limit = next(
            (item for item in self.route_limits if item.matches(request)),
            None,
        )
        if route_limit is None:
            return await call_next(request)

        try:
            decision = await self.limiter.check(
                route_limit.rule,
                principal=self._principal(request),
            )
        except ApplicationError as exc:
            return self._error_response(exc)

        headers = self._headers(
            limit=decision.limit,
            remaining=decision.remaining,
            retry_after=decision.retry_after_seconds,
        )
        if not decision.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Rate limit exceeded.",
                    "data": None,
                    "errors": [
                        {
                            "field": None,
                            "message": "Too many requests. Please retry later.",
                            "code": "RATE_LIMIT_EXCEEDED",
                        }
                    ],
                },
                headers=headers,
            )

        response = await call_next(request)
        for name, value in headers.items():
            response.headers[name] = value
        return response

    @staticmethod
    def _principal(request: Request) -> str:
        client_host = request.client.host if request.client else "unknown"
        authorization = request.headers.get("authorization", "")
        credential_hash = (
            hashlib.sha256(authorization.encode("utf-8")).hexdigest()
            if authorization
            else "anonymous"
        )
        return f"{client_host}:{credential_hash}"

    @staticmethod
    def _headers(
        *,
        limit: int,
        remaining: int,
        retry_after: int,
    ) -> dict[str, str]:
        result = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
        }
        if retry_after > 0:
            result["Retry-After"] = str(retry_after)
        return result

    @staticmethod
    def _error_response(exc: ApplicationError) -> JSONResponse:
        errors = [item.model_dump(mode="json") for item in (exc.errors or [])]
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message,
                "data": None,
                "errors": errors or None,
            },
        )


def default_route_rate_limits(
    *,
    api_prefix: str,
    limits: Mapping[str, int],
) -> tuple[RouteRateLimit, ...]:
    """Build the documented production limits using escaped route prefixes."""

    prefix = re.escape(api_prefix.rstrip("/"))
    return (
        RouteRateLimit.compile(
            methods={"POST"},
            path_pattern=rf"{prefix}/auth/(?:login|refresh)",
            name="authentication",
            limit=limits["login"],
            window_seconds=60,
        ),
        RouteRateLimit.compile(
            methods={"POST", "PUT"},
            path_pattern=rf"{prefix}/(?:document-files|documents)/(?:.*upload.*|.*files?.*)",
            name="upload",
            limit=limits["upload"],
            window_seconds=60,
        ),
        RouteRateLimit.compile(
            methods={"GET", "POST"},
            path_pattern=(
                rf"{prefix}/(?:(?:reports|compliance-reports|"
                r"advanced-reports)(?:/.*)?|.*(?:export|generate)(?:/.*)?)"
            ),
            name="reports",
            limit=limits["reports"],
            window_seconds=3600,
        ),
        RouteRateLimit.compile(
            methods={"POST"},
            path_pattern=(
                rf"{prefix}/(?:sharepoint/.*|document-files/[^/]+/"
                r"sharepoint/(?:push|pull|reconcile))"
            ),
            name="sharepoint-sync",
            limit=limits["sync"],
            window_seconds=3600,
        ),
        RouteRateLimit.compile(
            methods={"POST"},
            path_pattern=(
                rf"{prefix}/(?:integrations/sharepoint/connections/"
                r"[^/]+/test|admin/notification-templates/[^/]+/test)"
            ),
            name="sharepoint-connection-test",
            limit=limits["connection_test"],
            window_seconds=60,
        ),
        RouteRateLimit.compile(
            methods={"POST"},
            path_pattern=(
                rf"{prefix}/integrations/microsoft-graph/"
                r"(?:webhook|webhooks|notifications)"
            ),
            name="graph-webhook",
            limit=limits["sync"],
            window_seconds=3600,
        ),
    )
