"""SharePoint implementation of the private storage abstraction."""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from pathlib import PurePosixPath
from typing import Any, BinaryIO, ClassVar, cast
from uuid import UUID

from app.integrations.microsoft_graph.graph_error_mapper import GraphError
from app.integrations.microsoft_graph.sharepoint._paths import (
    join_remote_path,
    normalize_remote_path,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_download_service import (
    SharePointDownloadService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_file_service import (
    SharePointFileService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_folder_service import (
    SharePointFolderService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_upload_service import (
    SharePointUploadService,
)
from app.services.storage.base_storage import BaseStorage, StorageSaveResult


class SharePointStorageProvider(BaseStorage):
    """Keep Graph identifiers internal while streaming through the backend."""

    provider_name = "sharepoint"
    supports_versioning: ClassVar[bool] = True
    supports_restore: ClassVar[bool] = False
    supports_move: ClassVar[bool] = True
    supports_copy: ClassVar[bool] = True
    supports_remote_metadata: ClassVar[bool] = True
    supports_delta_sync: ClassVar[bool] = True

    def __init__(
        self,
        *,
        connection_id: UUID,
        drive_id: str,
        root_folder_path: str,
        uploads: SharePointUploadService,
        downloads: SharePointDownloadService,
        files: SharePointFileService,
        folders: SharePointFolderService,
        spool_max_memory_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self.connection_id = connection_id
        self.drive_id = drive_id.strip()
        self.root_folder_path = normalize_remote_path(root_folder_path)
        self.uploads = uploads
        self.downloads = downloads
        self.files = files
        self.folders = folders
        self.spool_max_memory_bytes = spool_max_memory_bytes

    async def save(
        self,
        source: BinaryIO,
        storage_key: str,
    ) -> StorageSaveResult:
        normalized = normalize_remote_path(storage_key, allow_root=False)
        size = self._remaining_size(source)
        metadata = await self.uploads.upload(
            drive_id=self.drive_id,
            remote_path=join_remote_path(
                self.root_folder_path,
                normalized,
            ),
            source=source,
            file_size=size,
        )
        remote_id = metadata.get("id")
        if not isinstance(remote_id, str) or not remote_id:
            raise ValueError("SharePoint upload returned no remote item ID.")
        return {
            "storage_key": normalized,
            "storage_provider": self.provider_name,
            "size": int(metadata.get("size", size)),
        }

    async def store(
        self,
        source: BinaryIO,
        storage_key: str,
    ) -> StorageSaveResult:
        return await self.save(source, storage_key)

    async def open(self, storage_key: str) -> BinaryIO:
        metadata = await self.get_metadata(storage_key)
        item_id = self._item_id(metadata)
        output = tempfile.SpooledTemporaryFile(  # noqa: SIM115
            max_size=self.spool_max_memory_bytes,
            mode="w+b",
        )
        try:
            async for chunk in self.downloads.stream(
                drive_id=self.drive_id,
                item_id=item_id,
            ):
                output.write(chunk)
            output.seek(0)
            return cast(BinaryIO, output)
        except Exception:
            output.close()
            raise

    async def stream(
        self,
        storage_key: str,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> AsyncIterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        metadata = await self.get_metadata(storage_key)
        download_service = SharePointDownloadService(
            self.downloads.client,
            chunk_size=chunk_size,
        )
        async for chunk in download_service.stream(
            drive_id=self.drive_id,
            item_id=self._item_id(metadata),
        ):
            yield chunk

    async def download(self, storage_key: str) -> BinaryIO:
        return await self.open(storage_key)

    async def exists(self, storage_key: str) -> bool:
        try:
            await self.get_metadata(storage_key)
            return True
        except GraphError as exc:
            if exc.status_code == 404:
                return False
            raise

    async def delete(self, storage_key: str) -> None:
        metadata = await self.get_metadata(storage_key)
        await self.files.delete(
            drive_id=self.drive_id,
            item_id=self._item_id(metadata),
            etag=self._etag(metadata),
        )

    async def restore(self, storage_key: str) -> None:
        raise NotImplementedError(
            "Graph v1.0 does not expose a safe drive-item recycle-bin restore."
        )

    async def move(
        self,
        source_key: str,
        destination_key: str,
    ) -> None:
        source = await self.get_metadata(source_key)
        destination = PurePosixPath(
            normalize_remote_path(destination_key, allow_root=False)
        )
        parent_path = join_remote_path(
            self.root_folder_path,
            destination.parent.as_posix()
            if destination.parent.as_posix() != "."
            else "",
        )
        parent = await self.folders.ensure_path(
            drive_id=self.drive_id,
            folder_path=parent_path,
        )
        await self.files.move(
            drive_id=self.drive_id,
            item_id=self._item_id(source),
            parent_item_id=self._item_id(parent),
            name=destination.name,
            etag=self._etag(source),
        )

    async def copy(
        self,
        source_key: str,
        destination_key: str,
    ) -> StorageSaveResult:
        source_size = await self.get_size(source_key)
        await self.copy_remote(source_key, destination_key)
        return {
            "storage_key": normalize_remote_path(
                destination_key,
                allow_root=False,
            ),
            "storage_provider": self.provider_name,
            "size": source_size,
        }

    async def copy_remote(
        self,
        source_key: str,
        destination_key: str,
    ) -> str | None:
        """Start the Graph-native asynchronous copy and return its monitor URL."""

        source = await self.get_metadata(source_key)
        destination = PurePosixPath(
            normalize_remote_path(destination_key, allow_root=False)
        )
        parent_path = join_remote_path(
            self.root_folder_path,
            destination.parent.as_posix()
            if destination.parent.as_posix() != "."
            else "",
        )
        parent = await self.folders.ensure_path(
            drive_id=self.drive_id,
            folder_path=parent_path,
        )
        return await self.files.copy(
            drive_id=self.drive_id,
            item_id=self._item_id(source),
            parent_item_id=self._item_id(parent),
            name=destination.name,
        )

    async def rename(
        self,
        source_key: str,
        destination_key: str,
    ) -> None:
        await self.move(source_key, destination_key)

    async def rename_remote(
        self,
        storage_key: str,
        new_name: str,
    ) -> dict[str, Any]:
        """Rename a drive item while returning Graph's safe item metadata."""

        metadata = await self.get_metadata(storage_key)
        return await self.files.rename(
            drive_id=self.drive_id,
            item_id=self._item_id(metadata),
            name=new_name,
            etag=self._etag(metadata),
        )

    async def get_metadata(self, storage_key: str) -> dict[str, Any]:
        normalized = normalize_remote_path(storage_key, allow_root=False)
        result = await self.folders.resolve_path(
            drive_id=self.drive_id,
            folder_path=join_remote_path(
                self.root_folder_path,
                normalized,
            ),
        )
        return result

    async def get_size(self, storage_key: str) -> int:
        metadata = await self.get_metadata(storage_key)
        return int(metadata.get("size", 0))

    def generate_internal_reference(
        self,
        storage_key: str,
    ) -> str:
        normalized = normalize_remote_path(storage_key, allow_root=False)
        return f"sharepoint://{self.connection_id}/{self.drive_id}/{normalized}"

    async def close(self) -> None:
        await self.uploads.client.close()

    @staticmethod
    def _remaining_size(source: BinaryIO) -> int:
        try:
            current = source.tell()
            source.seek(0, 2)
            end = source.tell()
            source.seek(current)
        except (AttributeError, OSError) as exc:
            raise ValueError(
                "SharePoint storage requires a seekable upload stream."
            ) from exc
        return max(0, end - current)

    @staticmethod
    def _item_id(metadata: dict[str, Any]) -> str:
        value = metadata.get("id")
        if not isinstance(value, str) or not value:
            raise ValueError("SharePoint item metadata has no identifier.")
        return value

    @staticmethod
    def _etag(metadata: dict[str, Any]) -> str | None:
        value = metadata.get("eTag")
        return value if isinstance(value, str) else None
