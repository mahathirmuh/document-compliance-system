"""Single authenticated HTTP boundary for all Microsoft Graph traffic."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx

from app.integrations.microsoft_graph.graph_error_mapper import (
    GraphError,
    map_graph_response,
    map_graph_transport_error,
)
from app.integrations.microsoft_graph.graph_rate_limit_service import (
    GraphRateLimitService,
)
from app.integrations.microsoft_graph.graph_retry_policy import (
    GraphRetryPolicy,
)


class GraphTokenProvider(Protocol):
    async def get_access_token(
        self,
        *,
        force_refresh: bool = False,
    ) -> str: ...


Sleep = Callable[[float], Awaitable[None]]


class GraphRequestService:
    """Authorize, correlate, throttle, retry, and sanitize Graph requests."""

    def __init__(
        self,
        *,
        auth_provider: GraphTokenProvider,
        base_url: str = "https://graph.microsoft.com/v1.0",
        timeout_seconds: float = 60,
        retry_policy: GraphRetryPolicy | None = None,
        rate_limits: GraphRateLimitService | None = None,
        http_client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Graph base URL must be an absolute HTTPS URL.")
        self.auth_provider = auth_provider
        self.base_url = base_url.rstrip("/") + "/"
        self._base_origin = (parsed.scheme.lower(), parsed.netloc.lower())
        self.retry_policy = retry_policy or GraphRetryPolicy()
        self.rate_limits = rate_limits or GraphRateLimitService()
        self._client = http_client or httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        self._owns_client = http_client is None
        self._sleep = sleep

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        content: bytes | bytearray | memoryview | None = None,
        headers: Mapping[str, str] | None = None,
        expected_statuses: set[int] | None = None,
        authenticate: bool = True,
        allow_external_hosts: tuple[str, ...] = (),
        stream_response: bool = False,
    ) -> httpx.Response:
        url = self._resolve_url(
            path_or_url,
            authenticate=authenticate,
            allow_external_hosts=allow_external_hosts,
        )
        expected = expected_statuses or set(range(200, 300))
        refreshed_authentication = False
        force_refresh = False
        attempt = 0
        while True:
            request_headers = {
                "Accept": "application/json",
                "client-request-id": str(uuid4()),
                "return-client-request-id": "true",
            }
            if json is not None:
                request_headers["Content-Type"] = "application/json"
            if headers:
                request_headers.update(
                    {
                        str(key): str(value)
                        for key, value in headers.items()
                        if key.lower() != "authorization"
                    }
                )
            if authenticate:
                token = await self.auth_provider.get_access_token(
                    force_refresh=force_refresh
                )
                force_refresh = False
                request_headers["Authorization"] = f"Bearer {token}"

            try:
                async with self.rate_limits.slot():
                    request = self._client.build_request(
                        method.upper(),
                        url,
                        params=params,
                        json=json,
                        content=content,
                        headers=request_headers,
                    )
                    response = await self._client.send(
                        request,
                        stream=stream_response,
                    )
            except (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError,
            ) as exc:
                decision = self.retry_policy.decide(
                    attempt=attempt,
                    status_code=None,
                    transient_transport_error=True,
                )
                await self.rate_limits.record(
                    retry_delay_seconds=(
                        decision.delay_seconds
                        if decision.should_retry
                        else None
                    )
                )
                if not decision.should_retry:
                    raise map_graph_transport_error(exc) from exc
                await self._sleep(decision.delay_seconds)
                attempt += 1
                continue

            await self.rate_limits.record(status_code=response.status_code)
            if response.status_code in expected:
                return response

            if (
                authenticate
                and response.status_code == 401
                and not refreshed_authentication
            ):
                await response.aclose()
                refreshed_authentication = True
                force_refresh = True
                continue

            decision = self.retry_policy.decide(
                attempt=attempt,
                status_code=response.status_code,
                retry_after=response.headers.get("Retry-After"),
            )
            if decision.should_retry:
                await self.rate_limits.record(
                    retry_delay_seconds=decision.delay_seconds
                )
                await response.aclose()
                await self._sleep(decision.delay_seconds)
                attempt += 1
                continue
            try:
                await response.aread()
                error = map_graph_response(response)
            finally:
                await response.aclose()
            raise error

    async def get_json(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self.request("GET", path_or_url, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise GraphError(
                map_graph_transport_error(exc).details
            ) from exc
        if not isinstance(payload, dict):
            raise GraphError(
                map_graph_transport_error(
                    ValueError("Graph returned a non-object response.")
                ).details
            )
        return payload

    async def request_external(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        expected_statuses: set[int] | None = None,
        stream_response: bool = False,
    ) -> httpx.Response:
        """Call a Graph-issued upload/download URL without bearer credentials."""

        return await self.request(
            method,
            url,
            content=content,
            headers=headers,
            expected_statuses=expected_statuses,
            authenticate=False,
            allow_external_hosts=(
                ".up.1drv.com",
                ".sharepoint.com",
                ".onedrive.com",
            ),
            stream_response=stream_response,
        )

    def _resolve_url(
        self,
        path_or_url: str,
        *,
        authenticate: bool,
        allow_external_hosts: tuple[str, ...],
    ) -> str:
        raw = path_or_url.strip()
        parsed = urlparse(raw)
        if not parsed.scheme:
            if not authenticate:
                raise ValueError("External Graph URLs must be absolute.")
            return urljoin(self.base_url, raw.lstrip("/"))
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError("Microsoft Graph requests require HTTPS.")
        origin = (parsed.scheme.lower(), parsed.netloc.lower())
        if authenticate and origin != self._base_origin:
            raise ValueError(
                "Bearer credentials cannot be sent outside the Graph origin."
            )
        if not authenticate:
            hostname = (parsed.hostname or "").lower()
            if not any(
                hostname == suffix.lstrip(".")
                or hostname.endswith(suffix.lower())
                for suffix in allow_external_hosts
            ):
                raise ValueError("The external Graph URL host is not trusted.")
        return raw
