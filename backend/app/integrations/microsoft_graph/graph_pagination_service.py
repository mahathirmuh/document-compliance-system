"""Bounded Graph @odata.nextLink traversal."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

from app.integrations.microsoft_graph.graph_client import GraphClient


class GraphPaginationService:
    def __init__(
        self,
        client: GraphClient,
        *,
        maximum_pages: int = 10_000,
    ) -> None:
        if maximum_pages <= 0:
            raise ValueError("maximum_pages must be positive.")
        self.client = client
        self.maximum_pages = maximum_pages
        base = urlparse(client.requests.base_url)
        self._graph_host = (base.hostname or "").lower()

    async def pages(self, initial_path: str) -> AsyncIterator[dict[str, Any]]:
        next_link: str | None = initial_path
        seen: set[str] = set()
        for _ in range(self.maximum_pages):
            if next_link is None:
                return
            if next_link in seen:
                raise ValueError("Graph pagination returned a repeated nextLink.")
            seen.add(next_link)
            page = await self.client.get(next_link)
            yield page
            value = page.get("@odata.nextLink")
            if value is None:
                return
            if not isinstance(value, str):
                raise TypeError("Graph nextLink must be a string.")
            parsed = urlparse(value)
            if (
                parsed.scheme.lower() != "https"
                or (parsed.hostname or "").lower() != self._graph_host
            ):
                raise ValueError("Graph nextLink points to an untrusted host.")
            next_link = value
        raise ValueError("Graph pagination exceeded the configured page limit.")

    async def collect_values(self, initial_path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        async for page in self.pages(initial_path):
            values = page.get("value", [])
            if not isinstance(values, list):
                raise TypeError("Graph collection response has invalid value.")
            items.extend(item for item in values if isinstance(item, dict))
        return items
