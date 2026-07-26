"""Phase 10 local-default and hybrid-storage regression tests."""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

import pytest

from app.services.storage.base_storage import BaseStorage, StorageSaveResult
from app.services.storage.hybrid_storage import HybridStorage
from app.services.storage.local_storage import LocalStorage
from app.services.storage.storage_factory import StorageFactory


class MemoryStorage(BaseStorage):
    provider_name = "remote"

    def __init__(self, *, fail_save: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_save = fail_save

    async def save(
        self,
        source: BinaryIO,
        storage_key: str,
    ) -> StorageSaveResult:
        if self.fail_save:
            raise OSError("remote unavailable")
        content = source.read()
        self.objects[storage_key] = content
        return {
            "storage_key": storage_key,
            "storage_provider": self.provider_name,
            "size": len(content),
        }

    async def open(self, storage_key: str) -> BinaryIO:
        return BytesIO(self.objects[storage_key])

    async def exists(self, storage_key: str) -> bool:
        return storage_key in self.objects

    async def delete(self, storage_key: str) -> None:
        self.objects.pop(storage_key, None)

    async def move(self, source_key: str, destination_key: str) -> None:
        self.objects[destination_key] = self.objects.pop(source_key)

    async def get_size(self, storage_key: str) -> int:
        return len(self.objects[storage_key])


def test_storage_factory_keeps_local_as_default(tmp_path) -> None:
    storage = StorageFactory.create("local", tmp_path)

    assert isinstance(storage, LocalStorage)
    assert storage.provider_name == "local"


@pytest.mark.asyncio
async def test_hybrid_storage_mirrors_and_prefers_local(tmp_path) -> None:
    remote = MemoryStorage()
    storage = StorageFactory.create(
        "hybrid",
        tmp_path,
        remote_storage=remote,
    )

    result = await storage.save(BytesIO(b"safe-content"), "docs/file.pdf")

    assert isinstance(storage, HybridStorage)
    assert result == {
        "storage_key": "docs/file.pdf",
        "storage_provider": "hybrid",
        "size": 12,
    }
    assert remote.objects["docs/file.pdf"] == b"safe-content"
    stream = await storage.open("docs/file.pdf")
    try:
        assert stream.read() == b"safe-content"
    finally:
        stream.close()


@pytest.mark.asyncio
async def test_hybrid_remote_failure_preserves_recoverable_local_copy(
    tmp_path,
) -> None:
    storage = HybridStorage(
        local=LocalStorage(tmp_path),
        remote=MemoryStorage(fail_save=True),
    )

    result = await storage.save(BytesIO(b"recoverable"), "docs/file.pdf")

    assert result["storage_provider"] == "hybrid"
    assert await storage.local.exists("docs/file.pdf")
    stream = await storage.open("docs/file.pdf")
    try:
        assert stream.read() == b"recoverable"
    finally:
        stream.close()
