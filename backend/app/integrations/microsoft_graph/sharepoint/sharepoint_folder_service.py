"""SharePoint folder browse, resolution, and controlled creation."""

from __future__ import annotations

from typing import Any

from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.graph_pagination_service import (
    GraphPaginationService,
)
from app.integrations.microsoft_graph.sharepoint._paths import (
    encode_identifier,
    encode_remote_path,
    normalize_remote_path,
)


class SharePointFolderService:
    def __init__(self, client: GraphClient) -> None:
        self.client = client
        self.pagination = GraphPaginationService(client)

    async def list_children(
        self,
        *,
        drive_id: str,
        folder_id: str | None = None,
        folder_path: str | None = None,
    ) -> list[dict[str, Any]]:
        drive = encode_identifier(drive_id)
        if folder_id:
            path = (
                f"/drives/{drive}/items/"
                f"{encode_identifier(folder_id)}/children"
            )
        else:
            normalized = normalize_remote_path(folder_path or "")
            path = (
                f"/drives/{drive}/root/children"
                if not normalized
                else (
                    f"/drives/{drive}/root:/"
                    f"{encode_remote_path(normalized)}:/children"
                )
            )
        return await self.pagination.collect_values(path)

    async def resolve_path(
        self,
        *,
        drive_id: str,
        folder_path: str,
    ) -> dict[str, Any]:
        normalized = normalize_remote_path(folder_path)
        if not normalized:
            return await self.client.get(
                f"/drives/{encode_identifier(drive_id)}/root"
            )
        return await self.client.get(
            f"/drives/{encode_identifier(drive_id)}/root:/"
            f"{encode_remote_path(normalized)}"
        )

    async def create_folder(
        self,
        *,
        drive_id: str,
        name: str,
        parent_item_id: str | None = None,
        conflict_behavior: str = "fail",
    ) -> dict[str, Any]:
        normalized_name = name.strip()
        if (
            not normalized_name
            or "/" in normalized_name
            or "\\" in normalized_name
            or normalized_name in {".", ".."}
        ):
            raise ValueError("SharePoint folder name is invalid.")
        if conflict_behavior not in {"fail", "rename", "replace"}:
            raise ValueError("Invalid SharePoint conflict behavior.")
        drive = encode_identifier(drive_id)
        endpoint = (
            f"/drives/{drive}/items/"
            f"{encode_identifier(parent_item_id)}/children"
            if parent_item_id
            else f"/drives/{drive}/root/children"
        )
        return await self.client.post(
            endpoint,
            payload={
                "name": normalized_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": conflict_behavior,
            },
            expected_statuses={200, 201},
        )

    async def ensure_path(
        self,
        *,
        drive_id: str,
        folder_path: str,
    ) -> dict[str, Any]:
        normalized = normalize_remote_path(folder_path)
        parent_id: str | None = None
        result: dict[str, Any] | None = None
        for segment in normalized.split("/") if normalized else []:
            children = await self.list_children(
                drive_id=drive_id,
                folder_id=parent_id,
            )
            result = next(
                (
                    item
                    for item in children
                    if "folder" in item
                    and str(item.get("name", "")).casefold()
                    == segment.casefold()
                ),
                None,
            )
            if result is None:
                result = await self.create_folder(
                    drive_id=drive_id,
                    name=segment,
                    parent_item_id=parent_id,
                )
            remote_id = result.get("id")
            if not isinstance(remote_id, str) or not remote_id:
                raise ValueError("Graph returned a folder without an identifier.")
            parent_id = remote_id
        return result or await self.resolve_path(
            drive_id=drive_id,
            folder_path="",
        )
