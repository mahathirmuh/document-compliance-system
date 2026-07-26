"""Provider-neutral contract for private physical-document storage."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, BinaryIO, TypedDict


class StorageSaveResult(TypedDict):
    """Infrastructure metadata returned after a completed streaming save."""

    storage_key: str
    storage_provider: str
    size: int


class BaseStorage(ABC):
    """Minimal private-storage interface used by document services."""

    provider_name = "unknown"
    supports_versioning = False
    supports_restore = False
    supports_move = True
    supports_copy = True
    supports_remote_metadata = False
    supports_delta_sync = False

    @abstractmethod
    async def save(
        self,
        source: BinaryIO,
        storage_key: str,
    ) -> StorageSaveResult:
        """Stream ``source`` to a new private object."""

    async def store(
        self,
        source: BinaryIO,
        storage_key: str,
    ) -> StorageSaveResult:
        """Backward-compatible semantic alias for ``save``."""
        return await self.save(source, storage_key)

    @abstractmethod
    async def open(self, storage_key: str) -> BinaryIO:
        """Open a private object for binary reading."""

    async def stream(
        self,
        storage_key: str,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> AsyncIterator[bytes]:
        """Yield a private object without loading it fully into memory."""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        source = await self.open(storage_key)
        try:
            while chunk := source.read(chunk_size):
                yield chunk
        finally:
            source.close()

    async def download(self, storage_key: str) -> BinaryIO:
        """Return a private binary stream for authenticated download."""
        return await self.open(storage_key)

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        """Return whether a regular object exists for ``storage_key``."""

    @abstractmethod
    async def delete(self, storage_key: str) -> None:
        """Delete an object idempotently."""

    @abstractmethod
    async def move(
        self,
        source_key: str,
        destination_key: str,
    ) -> None:
        """Move an object without exposing provider paths."""

    @abstractmethod
    async def get_size(self, storage_key: str) -> int:
        """Return object size in bytes."""

    async def restore(self, storage_key: str) -> None:
        """Restore a recoverable object when supported by the provider."""
        raise NotImplementedError(
            f"{self.provider_name} storage does not support restore."
        )

    async def copy(
        self,
        source_key: str,
        destination_key: str,
    ) -> StorageSaveResult:
        """Copy an object through bounded streaming."""
        source = await self.open(source_key)
        try:
            return await self.save(source, destination_key)
        finally:
            source.close()

    async def rename(
        self,
        source_key: str,
        destination_key: str,
    ) -> None:
        """Rename an object using provider-neutral move semantics."""
        await self.move(source_key, destination_key)

    async def get_metadata(self, storage_key: str) -> dict[str, Any]:
        """Return safe provider-neutral metadata."""
        return {
            "storageKey": storage_key,
            "storageProvider": self.provider_name,
            "size": await self.get_size(storage_key),
        }

    def generate_internal_reference(self, storage_key: str) -> str:
        """Create a non-public provider-qualified object reference."""
        return f"{self.provider_name}:{storage_key}"

    async def close(self) -> None:
        """Release provider-owned network resources when present."""
