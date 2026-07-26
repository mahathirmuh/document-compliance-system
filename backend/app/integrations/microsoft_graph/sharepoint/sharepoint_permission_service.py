"""Least-privilege SharePoint permission diagnostics."""

from __future__ import annotations

from typing import Any

from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.sharepoint._paths import (
    encode_identifier,
)


class SharePointPermissionService:
    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def list_site_permissions(
        self,
        site_id: str,
    ) -> list[dict[str, Any]]:
        payload = await self.client.get(
            f"/sites/{encode_identifier(site_id)}/permissions"
        )
        values = payload.get("value", [])
        if not isinstance(values, list):
            return []
        return [value for value in values if isinstance(value, dict)]

    async def test_read_write(
        self,
        *,
        site_id: str,
        drive_id: str,
    ) -> dict[str, bool]:
        await self.client.get(f"/sites/{encode_identifier(site_id)}")
        await self.client.get(f"/drives/{encode_identifier(drive_id)}/root")
        return {"siteRead": True, "driveRead": True}
