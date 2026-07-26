"""Small typed facade over the centralized Graph request service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from app.integrations.microsoft_graph.graph_request_service import (
    GraphRequestService,
)


class GraphClient:
    def __init__(self, requests: GraphRequestService) -> None:
        self.requests = requests

    async def get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.requests.get_json(path, params=params)

    async def post(
        self,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> dict[str, Any]:
        response = await self.requests.request(
            "POST",
            path,
            json=dict(payload or {}),
            expected_statuses=expected_statuses,
        )
        if response.status_code == 204 or not response.content:
            return {}
        value = response.json()
        return value if isinstance(value, dict) else {}

    async def put_bytes(
        self,
        path: str,
        content: bytes,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> dict[str, Any]:
        response = await self.requests.request(
            "PUT",
            path,
            params=params,
            content=content,
            headers=headers,
            expected_statuses=expected_statuses,
        )
        value = response.json()
        return value if isinstance(value, dict) else {}

    async def patch(
        self,
        path: str,
        *,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        response = await self.requests.request(
            "PATCH",
            path,
            json=dict(payload),
        )
        if not response.content:
            return {}
        value = response.json()
        return value if isinstance(value, dict) else {}

    async def delete(self, path: str) -> None:
        await self.requests.request(
            "DELETE",
            path,
            expected_statuses={200, 202, 204},
        )

    async def download(self, path: str) -> httpx.Response:
        """Return content or safely follow one Graph pre-authenticated redirect."""

        response = await self.requests.request(
            "GET",
            path,
            expected_statuses={200, 302, 303, 307, 308},
            headers={"Accept": "application/octet-stream"},
            stream_response=True,
        )
        if response.status_code == 200:
            return response
        location = response.headers.get("Location")
        if not location:
            await response.aclose()
            raise ValueError("Graph download redirect did not include a URL.")
        await response.aclose()
        return await self.requests.request_external(
            "GET",
            location,
            expected_statuses={200},
            headers={"Accept": "application/octet-stream"},
            stream_response=True,
        )

    async def close(self) -> None:
        await self.requests.close()
