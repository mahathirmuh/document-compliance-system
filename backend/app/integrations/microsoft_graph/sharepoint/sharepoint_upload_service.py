"""Streaming direct and resumable SharePoint uploads."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, BinaryIO

from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.graph_error_mapper import GraphError
from app.integrations.microsoft_graph.sharepoint._paths import (
    encode_identifier,
    encode_remote_path,
    normalize_remote_path,
)

GRAPH_UPLOAD_CHUNK_GRANULARITY = 320 * 1024


class SharePointUploadSessionExpired(RuntimeError):
    code = "SHAREPOINT_UPLOAD_SESSION_EXPIRED"


@dataclass(frozen=True, slots=True)
class UploadProgress:
    bytes_uploaded: int
    total_bytes: int


class SharePointUploadService:
    def __init__(
        self,
        client: GraphClient,
        *,
        simple_upload_max_bytes: int = 4 * 1024 * 1024,
        chunk_size_bytes: int = 10 * 1024 * 1024,
        maximum_file_size_bytes: int = 10 * 1024 * 1024 * 1024,
    ) -> None:
        if simple_upload_max_bytes <= 0:
            raise ValueError("Simple upload limit must be positive.")
        if (
            chunk_size_bytes <= 0
            or chunk_size_bytes % GRAPH_UPLOAD_CHUNK_GRANULARITY != 0
        ):
            raise ValueError(
                "Upload chunk size must be a positive multiple of 320 KiB."
            )
        self.client = client
        self.simple_upload_max_bytes = simple_upload_max_bytes
        self.chunk_size_bytes = chunk_size_bytes
        self.maximum_file_size_bytes = maximum_file_size_bytes

    async def upload(
        self,
        *,
        drive_id: str,
        remote_path: str,
        source: BinaryIO,
        file_size: int,
        conflict_behavior: str = "fail",
    ) -> dict[str, Any]:
        if file_size < 0 or file_size > self.maximum_file_size_bytes:
            raise ValueError("SharePoint upload size is outside policy.")
        if file_size <= self.simple_upload_max_bytes:
            content = await asyncio.to_thread(source.read, file_size + 1)
            if len(content) != file_size:
                raise ValueError("Upload source size changed during transfer.")
            return await self.upload_small(
                drive_id=drive_id,
                remote_path=remote_path,
                content=content,
                conflict_behavior=conflict_behavior,
            )
        return await self.upload_large(
            drive_id=drive_id,
            remote_path=remote_path,
            source=source,
            file_size=file_size,
            conflict_behavior=conflict_behavior,
        )

    async def upload_small(
        self,
        *,
        drive_id: str,
        remote_path: str,
        content: bytes,
        conflict_behavior: str = "fail",
    ) -> dict[str, Any]:
        if conflict_behavior not in {"fail", "replace", "rename"}:
            raise ValueError("Invalid SharePoint conflict behavior.")
        normalized = normalize_remote_path(remote_path, allow_root=False)
        if len(content) > self.simple_upload_max_bytes:
            raise ValueError("Content exceeds the simple upload limit.")
        return await self.client.put_bytes(
            f"/drives/{encode_identifier(drive_id)}/root:/"
            f"{encode_remote_path(normalized)}:/content",
            content,
            params={
                "@microsoft.graph.conflictBehavior": conflict_behavior,
            },
            headers={"Content-Type": "application/octet-stream"},
            expected_statuses={200, 201},
        )

    async def create_upload_session(
        self,
        *,
        drive_id: str,
        remote_path: str,
        conflict_behavior: str,
    ) -> dict[str, Any]:
        if conflict_behavior not in {"fail", "replace", "rename"}:
            raise ValueError("Invalid SharePoint conflict behavior.")
        normalized = normalize_remote_path(remote_path, allow_root=False)
        return await self.client.post(
            f"/drives/{encode_identifier(drive_id)}/root:/"
            f"{encode_remote_path(normalized)}:/createUploadSession",
            payload={
                "item": {
                    "@microsoft.graph.conflictBehavior": conflict_behavior
                }
            },
            expected_statuses={200, 201},
        )

    async def upload_large(
        self,
        *,
        drive_id: str,
        remote_path: str,
        source: BinaryIO,
        file_size: int,
        conflict_behavior: str = "fail",
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        session = await self.create_upload_session(
            drive_id=drive_id,
            remote_path=remote_path,
            conflict_behavior=conflict_behavior,
        )
        upload_url = session.get("uploadUrl")
        if not isinstance(upload_url, str) or not upload_url:
            raise ValueError("Graph did not return an upload session URL.")
        offset = self._next_expected_offset(
            session,
            default_offset=0,
            file_size=file_size,
        )
        if offset:
            await asyncio.to_thread(source.seek, offset)
        stalled_responses = 0
        while offset < file_size:
            remaining = file_size - offset
            requested = min(self.chunk_size_bytes, remaining)
            chunk = await asyncio.to_thread(source.read, requested)
            if len(chunk) != requested:
                raise ValueError("Upload source ended before its declared size.")
            end = offset + len(chunk) - 1
            try:
                response = await self.client.requests.request_external(
                    "PUT",
                    upload_url,
                    content=chunk,
                    headers={
                        "Content-Length": str(len(chunk)),
                        "Content-Range": (
                            f"bytes {offset}-{end}/{file_size}"
                        ),
                        "Content-Type": "application/octet-stream",
                    },
                    expected_statuses={200, 201, 202},
                )
            except GraphError as exc:
                if exc.status_code in {404, 410}:
                    raise SharePointUploadSessionExpired(
                        "The SharePoint upload session expired."
                    ) from exc
                raise
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("Graph returned an invalid upload response.")
            if response.status_code in {200, 201}:
                if end + 1 != file_size:
                    raise ValueError(
                        "Graph finalized the upload before the source ended."
                    )
                offset = end + 1
            else:
                next_offset = self._next_expected_offset(
                    payload,
                    default_offset=end + 1,
                    file_size=file_size,
                )
                stalled_responses = (
                    stalled_responses + 1
                    if next_offset <= offset
                    else 0
                )
                if stalled_responses > 3:
                    raise ValueError(
                        "Graph upload session did not advance."
                    )
                if next_offset != end + 1:
                    await asyncio.to_thread(source.seek, next_offset)
                offset = next_offset
            if progress_callback is not None:
                result = progress_callback(
                    UploadProgress(
                        bytes_uploaded=offset,
                        total_bytes=file_size,
                    )
                )
                if hasattr(result, "__await__"):
                    await result
            if response.status_code in {200, 201}:
                remote_size = payload.get("size")
                if remote_size is not None and int(remote_size) != file_size:
                    raise ValueError(
                        "Final SharePoint size does not match the source."
                    )
                return payload
        raise ValueError("Graph upload session did not return final metadata.")

    @staticmethod
    def _next_expected_offset(
        payload: dict[str, Any],
        *,
        default_offset: int,
        file_size: int,
    ) -> int:
        ranges = payload.get("nextExpectedRanges")
        if ranges is None:
            return default_offset
        if (
            not isinstance(ranges, list)
            or not ranges
            or not isinstance(ranges[0], str)
        ):
            raise ValueError(
                "Graph returned invalid upload continuation ranges."
            )
        start = ranges[0].partition("-")[0]
        try:
            offset = int(start)
        except ValueError as exc:
            raise ValueError(
                "Graph returned an invalid upload continuation offset."
            ) from exc
        if offset < 0 or offset > file_size:
            raise ValueError(
                "Graph returned an upload continuation offset outside the file."
            )
        return offset

    @staticmethod
    def session_expired(
        expiration_datetime: str | None,
        *,
        now: datetime,
    ) -> bool:
        if not expiration_datetime:
            return False
        try:
            expiry = datetime.fromisoformat(
                expiration_datetime.replace("Z", "+00:00")
            )
        except ValueError:
            return False
        return expiry <= now
