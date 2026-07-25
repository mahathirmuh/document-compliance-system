"""Root-enforced local implementation of the private storage contract."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.services.storage.base_storage import (
    BaseStorage,
    StorageSaveResult,
)

DEFAULT_COPY_CHUNK_SIZE = 1024 * 1024


class UnsafeStorageKeyError(ValueError):
    """A storage key escaped, or could ambiguously escape, the root."""


class LocalStorage(BaseStorage):
    """Store private objects under one configured, non-public root."""

    provider_name = "local"

    def __init__(
        self,
        root: str | Path,
        *,
        copy_chunk_size: int = DEFAULT_COPY_CHUNK_SIZE,
    ) -> None:
        if copy_chunk_size <= 0:
            raise ValueError("copy_chunk_size must be positive.")
        self.root = Path(root).expanduser().resolve()
        self.copy_chunk_size = copy_chunk_size
        self._filesystem_path(self.root).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _filesystem_path(path: Path) -> Path:
        """Use Win32 extended paths without changing stored relative keys."""
        if os.name != "nt":
            return path
        raw_path = str(path)
        if raw_path.startswith("\\\\?\\"):
            return path
        if raw_path.startswith("\\\\"):
            return Path(f"\\\\?\\UNC\\{raw_path[2:]}")
        return Path(f"\\\\?\\{raw_path}")

    @staticmethod
    def normalize_key(storage_key: str) -> str:
        """Validate and normalize a provider-neutral POSIX object key."""
        if not isinstance(storage_key, str):
            raise UnsafeStorageKeyError("Storage key must be a string.")
        raw_key = storage_key.strip()
        if (
            not raw_key
            or "\x00" in raw_key
            or "\\" in raw_key
            or ":" in raw_key
            or any(
                part in {"", ".", ".."} for part in raw_key.split("/")
            )
        ):
            raise UnsafeStorageKeyError("Storage key is not a safe path.")

        path = PurePosixPath(raw_key)
        if path.is_absolute():
            raise UnsafeStorageKeyError("Storage key must remain relative.")
        return path.as_posix()

    def resolve_key(self, storage_key: str) -> Path:
        """Resolve a key and prove that it remains beneath ``root``."""
        normalized = self.normalize_key(storage_key)
        candidate = self.root.joinpath(
            *PurePosixPath(normalized).parts
        ).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise UnsafeStorageKeyError(
                "Storage key resolves outside the storage root."
            ) from exc
        return candidate

    async def save(
        self,
        source: BinaryIO,
        storage_key: str,
    ) -> StorageSaveResult:
        normalized = self.normalize_key(storage_key)
        size = await asyncio.to_thread(
            self._save_sync,
            source,
            normalized,
        )
        return {
            "storage_key": normalized,
            "storage_provider": self.provider_name,
            "size": size,
        }

    def _save_sync(self, source: BinaryIO, storage_key: str) -> int:
        destination = self.resolve_key(storage_key)
        filesystem_destination = self._filesystem_path(destination)
        filesystem_destination.parent.mkdir(parents=True, exist_ok=True)
        if filesystem_destination.exists():
            raise FileExistsError("Storage object already exists.")

        total = 0
        created = False
        try:
            with filesystem_destination.open("xb") as output:
                created = True
                while True:
                    chunk = source.read(self.copy_chunk_size)
                    if not chunk:
                        break
                    output.write(chunk)
                    total += len(chunk)
                output.flush()
            return total
        except Exception:
            if created:
                filesystem_destination.unlink(missing_ok=True)
            raise

    async def open(self, storage_key: str) -> BinaryIO:
        return await asyncio.to_thread(self._open_sync, storage_key)

    def _open_sync(self, storage_key: str) -> BinaryIO:
        path = self.resolve_key(storage_key)
        filesystem_path = self._filesystem_path(path)
        if not filesystem_path.is_file():
            raise FileNotFoundError("Storage object does not exist.")
        return filesystem_path.open("rb")

    async def exists(self, storage_key: str) -> bool:
        return await asyncio.to_thread(self._exists_sync, storage_key)

    def _exists_sync(self, storage_key: str) -> bool:
        path = self.resolve_key(storage_key)
        return self._filesystem_path(path).is_file()

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(self._delete_sync, storage_key)

    def _delete_sync(self, storage_key: str) -> None:
        path = self.resolve_key(storage_key)
        filesystem_path = self._filesystem_path(path)
        if filesystem_path.exists() and not filesystem_path.is_file():
            raise IsADirectoryError("Storage key does not identify a file.")
        filesystem_path.unlink(missing_ok=True)
        self._prune_empty_parents(path.parent)

    async def move(
        self,
        source_key: str,
        destination_key: str,
    ) -> None:
        await asyncio.to_thread(
            self._move_sync,
            source_key,
            destination_key,
        )

    def _move_sync(
        self,
        source_key: str,
        destination_key: str,
    ) -> None:
        source = self.resolve_key(source_key)
        destination = self.resolve_key(destination_key)
        if source == destination:
            return
        filesystem_source = self._filesystem_path(source)
        filesystem_destination = self._filesystem_path(destination)
        if not filesystem_source.is_file():
            raise FileNotFoundError("Source storage object does not exist.")
        filesystem_destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        if filesystem_destination.exists():
            raise FileExistsError("Destination storage object already exists.")
        filesystem_source.replace(filesystem_destination)
        self._prune_empty_parents(source.parent)

    async def get_size(self, storage_key: str) -> int:
        return await asyncio.to_thread(self._get_size_sync, storage_key)

    def _get_size_sync(self, storage_key: str) -> int:
        path = self.resolve_key(storage_key)
        filesystem_path = self._filesystem_path(path)
        if not filesystem_path.is_file():
            raise FileNotFoundError("Storage object does not exist.")
        return filesystem_path.stat().st_size

    def _prune_empty_parents(self, directory: Path) -> None:
        current = directory
        while current != self.root:
            try:
                self._filesystem_path(current).rmdir()
            except (FileNotFoundError, OSError):
                break
            current = current.parent
