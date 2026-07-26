"""Authenticated backend-only SharePoint download streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.sharepoint._paths import (
    encode_identifier,
)


class SharePointDownloadService:
    def __init__(
        self,
        client: GraphClient,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("Download chunk size must be positive.")
        self.client = client
        self.chunk_size = chunk_size

    async def stream(
        self,
        *,
        drive_id: str,
        item_id: str,
    ) -> AsyncIterator[bytes]:
        response = await self.client.download(
            f"/drives/{encode_identifier(drive_id)}/items/"
            f"{encode_identifier(item_id)}/content"
        )
        try:
            async for chunk in response.aiter_bytes(self.chunk_size):
                if chunk:
                    yield chunk
        finally:
            await response.aclose()
