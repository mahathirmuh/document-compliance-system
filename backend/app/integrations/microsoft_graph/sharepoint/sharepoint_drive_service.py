"""Resolve one SharePoint document library drive."""

from __future__ import annotations

from typing import Any

from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.graph_pagination_service import (
    GraphPaginationService,
)
from app.integrations.microsoft_graph.sharepoint._paths import (
    encode_identifier,
)


class SharePointDriveService:
    def __init__(self, client: GraphClient) -> None:
        self.client = client
        self.pagination = GraphPaginationService(client)

    async def list_drives(self, site_id: str) -> list[dict[str, Any]]:
        return await self.pagination.collect_values(
            f"/sites/{encode_identifier(site_id)}/drives"
        )

    async def resolve_drive(
        self,
        *,
        site_id: str,
        drive_id: str | None = None,
        library_name: str | None = None,
    ) -> dict[str, Any]:
        if drive_id:
            return await self.client.get(
                f"/drives/{encode_identifier(drive_id)}"
            )
        if not library_name or not library_name.strip():
            raise ValueError("A drive identifier or library name is required.")
        expected = library_name.strip().casefold()
        matches = [
            drive
            for drive in await self.list_drives(site_id)
            if str(drive.get("name", "")).strip().casefold() == expected
        ]
        if len(matches) != 1:
            raise LookupError(
                "The configured SharePoint library was not uniquely resolved."
            )
        return matches[0]
