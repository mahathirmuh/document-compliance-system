"""Resolve configured SharePoint sites without tenant-wide enumeration."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.integrations.microsoft_graph.graph_client import GraphClient


class SharePointSiteService:
    def __init__(self, client: GraphClient) -> None:
        self.client = client

    async def resolve_site(
        self,
        *,
        hostname: str,
        site_path: str,
    ) -> dict[str, Any]:
        normalized_host = hostname.strip().lower()
        if (
            not normalized_host
            or "/" in normalized_host
            or "\\" in normalized_host
        ):
            raise ValueError("SharePoint hostname is invalid.")
        normalized_path = site_path.strip().strip("/")
        if not normalized_path:
            raise ValueError("SharePoint site path is required.")
        encoded_path = "/".join(
            quote(part, safe="")
            for part in normalized_path.split("/")
            if part
        )
        return await self.client.get(
            f"/sites/{quote(normalized_host, safe='.')}:/{encoded_path}"
        )

    async def get_site(self, site_id: str) -> dict[str, Any]:
        from app.integrations.microsoft_graph.sharepoint._paths import (
            encode_identifier,
        )

        return await self.client.get(
            f"/sites/{encode_identifier(site_id)}"
        )
