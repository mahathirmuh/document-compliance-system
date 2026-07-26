"""Drive-item delta traversal that commits no token prematurely."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.graph_error_mapper import GraphError
from app.integrations.microsoft_graph.sharepoint._paths import (
    encode_identifier,
)


class SharePointDeltaTokenInvalid(RuntimeError):
    code = "SHAREPOINT_DELTA_TOKEN_INVALID"


@dataclass(frozen=True, slots=True)
class SharePointDeltaPageResult:
    items: tuple[dict[str, Any], ...]
    delta_link: str
    page_count: int


class SharePointDeltaService:
    def __init__(
        self,
        client: GraphClient,
        *,
        maximum_pages: int = 10_000,
    ) -> None:
        self.client = client
        self.maximum_pages = maximum_pages

    async def collect_changes(
        self,
        *,
        drive_id: str,
        folder_item_id: str | None = None,
        delta_link: str | None = None,
    ) -> SharePointDeltaPageResult:
        if delta_link:
            next_link = delta_link
        elif folder_item_id:
            next_link = (
                f"/drives/{encode_identifier(drive_id)}/items/"
                f"{encode_identifier(folder_item_id)}/delta"
            )
        else:
            next_link = (
                f"/drives/{encode_identifier(drive_id)}/root/delta"
            )
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_number in range(1, self.maximum_pages + 1):
            if next_link in seen:
                raise ValueError("Graph delta pagination repeated a link.")
            seen.add(next_link)
            try:
                page = await self.client.get(next_link)
            except GraphError as exc:
                if exc.status_code in {400, 404, 410}:
                    raise SharePointDeltaTokenInvalid(
                        "The SharePoint delta state is no longer valid."
                    ) from exc
                raise
            values = page.get("value", [])
            if not isinstance(values, list):
                raise TypeError("Graph delta response has invalid value.")
            items.extend(item for item in values if isinstance(item, dict))
            delta = page.get("@odata.deltaLink")
            if isinstance(delta, str) and delta:
                return SharePointDeltaPageResult(
                    items=tuple(items),
                    delta_link=delta,
                    page_count=page_number,
                )
            following = page.get("@odata.nextLink")
            if not isinstance(following, str) or not following:
                raise ValueError(
                    "Graph delta response contained neither nextLink nor deltaLink."
                )
            next_link = following
        raise ValueError("Graph delta response exceeded the page limit.")
