"""Provider-neutral contract for private physical-document storage."""

from abc import ABC, abstractmethod
from typing import BinaryIO, TypedDict


class StorageSaveResult(TypedDict):
    """Infrastructure metadata returned after a completed streaming save."""

    storage_key: str
    storage_provider: str
    size: int


class BaseStorage(ABC):
    """Minimal private-storage interface used by document services."""

    @abstractmethod
    async def save(
        self,
        source: BinaryIO,
        storage_key: str,
    ) -> StorageSaveResult:
        """Stream ``source`` to a new private object."""

    @abstractmethod
    async def open(self, storage_key: str) -> BinaryIO:
        """Open a private object for binary reading."""

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
