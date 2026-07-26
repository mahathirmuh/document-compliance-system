"""Metadata and mutation operations for SharePoint drive items."""

from __future__ import annotations

from typing import Any

from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.graph_pagination_service import (
    GraphPaginationService,
)
from app.integrations.microsoft_graph.sharepoint._paths import (
    encode_identifier,
)


class SharePointFileService:
    def __init__(self, client: GraphClient) -> None:
        self.client = client
        self.pagination = GraphPaginationService(client)

    def item_path(self, drive_id: str, item_id: str) -> str:
        return (
            f"/drives/{encode_identifier(drive_id)}/items/"
            f"{encode_identifier(item_id)}"
        )

    async def get_metadata(
        self,
        *,
        drive_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        return await self.client.get(self.item_path(drive_id, item_id))

    async def list_versions(
        self,
        *,
        drive_id: str,
        item_id: str,
    ) -> list[dict[str, Any]]:
        return await self.pagination.collect_values(
            f"{self.item_path(drive_id, item_id)}/versions"
        )

    async def rename(
        self,
        *,
        drive_id: str,
        item_id: str,
        name: str,
        etag: str | None = None,
    ) -> dict[str, Any]:
        headers = {"If-Match": etag} if etag else None
        response = await self.client.requests.request(
            "PATCH",
            self.item_path(drive_id, item_id),
            json={"name": self._safe_name(name)},
            headers=headers,
        )
        value = response.json()
        return value if isinstance(value, dict) else {}

    async def move(
        self,
        *,
        drive_id: str,
        item_id: str,
        parent_item_id: str,
        name: str | None = None,
        etag: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parentReference": {"id": parent_item_id.strip()}
        }
        if name is not None:
            payload["name"] = self._safe_name(name)
        headers = {"If-Match": etag} if etag else None
        response = await self.client.requests.request(
            "PATCH",
            self.item_path(drive_id, item_id),
            json=payload,
            headers=headers,
        )
        value = response.json()
        return value if isinstance(value, dict) else {}

    async def copy(
        self,
        *,
        drive_id: str,
        item_id: str,
        parent_item_id: str,
        name: str | None = None,
    ) -> str | None:
        payload: dict[str, Any] = {
            "parentReference": {"id": parent_item_id.strip()}
        }
        if name is not None:
            payload["name"] = self._safe_name(name)
        response = await self.client.requests.request(
            "POST",
            f"{self.item_path(drive_id, item_id)}/copy",
            json=payload,
            expected_statuses={200, 201, 202},
        )
        return response.headers.get("Location")

    async def delete(
        self,
        *,
        drive_id: str,
        item_id: str,
        etag: str | None = None,
    ) -> None:
        await self.client.requests.request(
            "DELETE",
            self.item_path(drive_id, item_id),
            headers={"If-Match": etag} if etag else None,
            expected_statuses={200, 202, 204},
        )

    @staticmethod
    def _safe_name(name: str) -> str:
        normalized = name.strip()
        if (
            not normalized
            or "/" in normalized
            or "\\" in normalized
            or normalized in {".", ".."}
        ):
            raise ValueError("SharePoint item name is invalid.")
        return normalized
