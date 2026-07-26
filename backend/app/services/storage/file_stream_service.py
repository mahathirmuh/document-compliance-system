"""Thread-offloaded bounded streaming helpers for storage objects."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import BinaryIO

from app.services.storage.base_storage import (
    BaseStorage,
    StorageSaveResult,
)


class StreamLimitExceededError(ValueError):
    """A streamed upload exceeded its configured byte ceiling."""


class _LimitedReader:
    def __init__(self, source: BinaryIO, max_bytes: int) -> None:
        self.source = source
        self.max_bytes = max_bytes
        self.total = 0

    def read(self, size: int = -1) -> bytes:
        remaining_with_probe = self.max_bytes - self.total + 1
        requested = (
            remaining_with_probe if size < 0 else min(size, remaining_with_probe)
        )
        chunk = self.source.read(requested)
        self.total += len(chunk)
        if self.total > self.max_bytes:
            raise StreamLimitExceededError(
                "Stream exceeds the configured maximum size."
            )
        return chunk


class FileStreamService:
    """Bound upload writes and avoid blocking download reads."""

    @staticmethod
    async def save_with_limit(
        storage: BaseStorage,
        source: BinaryIO,
        storage_key: str,
        *,
        max_bytes: int,
    ) -> StorageSaveResult:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive.")
        limited = _LimitedReader(source, max_bytes)
        return await storage.save(limited, storage_key)

    @staticmethod
    async def iter_storage(
        storage: BaseStorage,
        storage_key: str,
        *,
        chunk_size: int,
    ) -> AsyncIterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        stream = await storage.open(storage_key)
        try:
            while True:
                chunk = await asyncio.to_thread(stream.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(stream.close)


async def stream_storage(
    storage: BaseStorage,
    storage_key: str,
    *,
    chunk_size: int,
) -> AsyncIterator[bytes]:
    """Module-level async generator suitable for ``StreamingResponse``."""
    async for chunk in FileStreamService.iter_storage(
        storage,
        storage_key,
        chunk_size=chunk_size,
    ):
        yield chunk
