"""Local-first storage with a SharePoint mirror and safe read fallback."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, BinaryIO, ClassVar

from app.services.storage.base_storage import BaseStorage, StorageSaveResult

logger = logging.getLogger(__name__)


class HybridStorage(BaseStorage):
    """Keep a durable local copy while mirroring to remote storage when possible.

    A remote write failure intentionally does not delete the completed local
    object. The document remains recoverable with ``NOT_SYNCED`` status and can
    be reconciled by the SharePoint worker.
    """

    provider_name = "hybrid"
    supports_versioning: ClassVar[bool] = True
    supports_restore: ClassVar[bool] = True
    supports_move: ClassVar[bool] = True
    supports_copy: ClassVar[bool] = True
    supports_remote_metadata: ClassVar[bool] = True
    supports_delta_sync: ClassVar[bool] = True

    def __init__(
        self,
        *,
        local: BaseStorage,
        remote: BaseStorage,
    ) -> None:
        if local.provider_name == remote.provider_name:
            raise ValueError("Hybrid storage requires distinct providers.")
        self.local = local
        self.remote = remote

    async def save(
        self,
        source: BinaryIO,
        storage_key: str,
    ) -> StorageSaveResult:
        starting_position = self._position(source)
        local_result = await self.local.save(source, storage_key)
        try:
            source.seek(starting_position)
            await self.remote.save(source, storage_key)
        except Exception:  # noqa: BLE001 - local copy is the recovery boundary
            logger.warning(
                "Hybrid remote mirror write failed; reconciliation is required.",
                extra={"event": "hybrid_remote_write_failed"},
            )
        return {
            "storage_key": local_result["storage_key"],
            "storage_provider": self.provider_name,
            "size": local_result["size"],
        }

    async def open(self, storage_key: str) -> BinaryIO:
        if await self.local.exists(storage_key):
            return await self.local.open(storage_key)
        return await self.remote.open(storage_key)

    async def stream(
        self,
        storage_key: str,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> AsyncIterator[bytes]:
        provider = self.local if await self.local.exists(storage_key) else self.remote
        async for chunk in provider.stream(storage_key, chunk_size=chunk_size):
            yield chunk

    async def exists(self, storage_key: str) -> bool:
        return await self.local.exists(storage_key) or await self.remote.exists(
            storage_key
        )

    async def delete(self, storage_key: str) -> None:
        if await self.local.exists(storage_key):
            await self.local.delete(storage_key)
        if await self.remote.exists(storage_key):
            await self.remote.delete(storage_key)

    async def move(
        self,
        source_key: str,
        destination_key: str,
    ) -> None:
        if await self.local.exists(source_key):
            await self.local.move(source_key, destination_key)
        if await self.remote.exists(source_key):
            await self.remote.move(source_key, destination_key)

    async def restore(self, storage_key: str) -> None:
        await self.local.restore(storage_key)

    async def copy(
        self,
        source_key: str,
        destination_key: str,
    ) -> StorageSaveResult:
        local_result = await self.local.copy(source_key, destination_key)
        try:
            if await self.remote.exists(source_key):
                await self.remote.copy(source_key, destination_key)
        except Exception:  # noqa: BLE001 - reconcile repairs the remote mirror
            logger.warning(
                "Hybrid remote mirror copy failed; reconciliation is required.",
                extra={"event": "hybrid_remote_copy_failed"},
            )
        return {
            "storage_key": local_result["storage_key"],
            "storage_provider": self.provider_name,
            "size": local_result["size"],
        }

    async def get_size(self, storage_key: str) -> int:
        if await self.local.exists(storage_key):
            return await self.local.get_size(storage_key)
        return await self.remote.get_size(storage_key)

    async def get_metadata(self, storage_key: str) -> dict[str, Any]:
        local_exists = await self.local.exists(storage_key)
        remote_exists = await self.remote.exists(storage_key)
        if not local_exists and not remote_exists:
            raise FileNotFoundError("Storage object does not exist.")
        return {
            "storageKey": storage_key,
            "storageProvider": self.provider_name,
            "size": await self.get_size(storage_key),
            "localAvailable": local_exists,
            "remoteAvailable": remote_exists,
        }

    def generate_internal_reference(self, storage_key: str) -> str:
        return f"hybrid:{storage_key}"

    async def close(self) -> None:
        await self.local.close()
        await self.remote.close()

    @staticmethod
    def _position(source: BinaryIO) -> int:
        try:
            return source.tell()
        except (AttributeError, OSError) as exc:
            raise ValueError(
                "Hybrid storage requires a seekable upload stream."
            ) from exc
